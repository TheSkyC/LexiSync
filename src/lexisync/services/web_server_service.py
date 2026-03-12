# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import asyncio
import hashlib
import logging
import os
import socket
import time
import uuid
import weakref

from fastapi import Depends, FastAPI, HTTPException, Security, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import APIKeyQuery
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PySide6.QtCore import QObject, QThread, Signal
import uvicorn

from lexisync.utils.localization import _
from lexisync.utils.path_utils import get_resource_path

logger = logging.getLogger(__name__)

# ─── Auth Utils ────────────────────────────────────────────────────────────────


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, _ = hashed.split("$")
        h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return f"{salt}${h}" == hashed
    except ValueError:
        return False


# ─── Request Models ────────────────────────────────────────────────────────────


class RememberMeLoginRequest(BaseModel):
    remember_token: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenLoginRequest(BaseModel):
    token: str
    display_name: str


class TranslationUpdate(BaseModel):
    ts_id: str
    new_text: str | None = None
    is_reviewed: bool | None = None
    is_fuzzy: bool | None = None
    plural_index: int = 0
    user: str = "Web User"


class AITranslateRequest(BaseModel):
    ts_id: str


# ─── Connection Manager ────────────────────────────────────────────────────────


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.active_editors: dict[str, dict[str, float]] = {}
        self._ws_user: dict[int, dict] = {}  # id -> {"name": str, "role": str}

    async def connect(self, websocket: WebSocket, user_info: dict):
        self.active_connections.append(websocket)
        self._ws_user[id(websocket)] = user_info

    def disconnect(self, websocket: WebSocket) -> dict | None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        return self._ws_user.pop(id(websocket), None)

    def get_online_users(self) -> list[dict]:
        unique_users = {}
        for info in self._ws_user.values():
            unique_users[info["name"]] = info
        return list(unique_users.values())

    def cleanup_user_editors(self, username: str) -> list[str]:
        affected = []
        for ts_id, editors in list(self.active_editors.items()):
            if username in editors:
                editors.pop(username, None)
                affected.append(ts_id)
            if not editors:
                del self.active_editors[ts_id]
        return affected

    async def broadcast_json(self, message: dict):
        dead = []
        for ws in list(self.active_connections):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# ─── Qt Signals ────────────────────────────────────────────────────────────────


class WebServerSignals(QObject):
    update_requested = Signal(object)
    focus_changed = Signal(str, str)
    server_started = Signal(str)
    server_stopped = Signal()
    ai_translate_requested = Signal(str)


# ─── Web Server Service ────────────────────────────────────────────────────────


class WebServerService(QThread):
    def __init__(self, app_instance):
        super().__init__()
        self.app_ref = weakref.ref(app_instance)
        self.signals = WebServerSignals()
        self.port = 20455
        self.host = "0.0.0.0"
        self.is_running = False
        self.loop = None

        # 内存 Session 存储: session_id -> {"name": "...", "role": "..."}
        self.sessions = {}

        self.update_auth_data(app_instance.config.get("cloud_users", []), app_instance.config.get("cloud_tokens", []))

        self.ws_manager = ConnectionManager()
        self.fastapi_app = FastAPI()

        self.fastapi_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._setup_routes()

    def update_auth_data(self, users: list, tokens: list):
        self.cloud_users = users
        self.cloud_tokens = tokens

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _verify_session(self, token: str | None = Security(APIKeyQuery(name="token", auto_error=False))):
        if not token or token not in self.sessions:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        return self.sessions[token]

    def _get_main_app(self):
        app = self.app_ref()
        if not app:
            raise HTTPException(status_code=503, detail="Application unavailable")
        return app

    @staticmethod
    def _apply_status_filter(data: list, status: str | None) -> list:
        if not status or status == "all":
            return data
        if status == "reviewed":
            return [ts for ts in data if ts.is_reviewed]
        if status == "fuzzy":
            return [ts for ts in data if ts.is_fuzzy and not ts.is_reviewed]
        if status == "translated":
            return [ts for ts in data if ts.translation and not ts.is_reviewed and not ts.is_fuzzy]
        if status == "untranslated":
            return [ts for ts in data if not ts.translation and not ts.is_reviewed and not ts.is_fuzzy]
        return data

    # ── Routes ─────────────────────────────────────────────────────────────────

    def _setup_routes(self):
        app = self.fastapi_app
        main_app = self._get_main_app()

        @app.on_event("startup")
        async def startup_event():
            self.loop = asyncio.get_running_loop()

        # ── Auth Endpoints ─────────────────────────────────────────────────────

        @app.post("/api/v1/login")
        async def login_account(req: LoginRequest):
            for u in self.cloud_users:
                if u["username"] == req.username:
                    if verify_password(req.password, u["password_hash"]):
                        session_id = str(uuid.uuid4())
                        self.sessions[session_id] = {"name": u["username"], "role": u["role"]}
                        return {"token": session_id, "name": u["username"], "role": u["role"]}
            raise HTTPException(status_code=401, detail="Invalid username or password")

        @app.post("/api/v1/login-remembered")
        async def login_remembered(req: RememberMeLoginRequest):
            try:
                username, host_token = req.remember_token.split(":", 1)
            except (ValueError, AttributeError) as e:
                raise HTTPException(status_code=400, detail="Invalid remember_token format") from e

            if host_token != main_app.cloud_token:
                raise HTTPException(status_code=401, detail="Host has been restarted or token is invalid")

            user_data = next((u for u in self.cloud_users if u["username"] == username), None)
            if not user_data:
                raise HTTPException(status_code=401, detail="User not found")

            session_id = str(uuid.uuid4())
            self.sessions[session_id] = {"name": user_data["username"], "role": user_data["role"]}
            return {"token": session_id, "name": user_data["username"], "role": user_data["role"]}

        @app.post("/api/v1/login-token")
        async def login_token(req: TokenLoginRequest):
            current_time = time.time()
            for t in self.cloud_tokens:
                if t["token"] == req.token:
                    if t.get("expires_at") and current_time > t["expires_at"]:
                        raise HTTPException(status_code=401, detail="Token has expired")

                    session_id = str(uuid.uuid4())
                    display_name = req.display_name.strip() or "Guest"
                    self.sessions[session_id] = {"name": display_name, "role": t["role"]}
                    return {"token": session_id, "name": display_name, "role": t["role"]}
            raise HTTPException(status_code=401, detail="Invalid access token")

        @app.get("/api/v1/me")
        async def get_me(user: dict = Depends(self._verify_session)):
            return user

        # ── WebSocket ──────────────────────────────────────────────────────────

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket, token: str | None = None):
            await websocket.accept()

            if not token or token not in self.sessions:
                await websocket.close(code=1008)
                return

            user_info = self.sessions[token]
            username = user_info["name"]
            role = user_info["role"]

            self.ws_manager.active_connections.append(websocket)
            self.ws_manager._ws_user[id(websocket)] = user_info

            await self.ws_manager.broadcast_json(
                {
                    "type": "USER_CONNECTED",
                    "data": {
                        "user": username,
                        "role": role,
                        "online_users": self.ws_manager.get_online_users(),
                    },
                }
            )

            try:
                while True:
                    data = await websocket.receive_json()
                    action = data.get("action")

                    if action == "focus":
                        ts_id = data.get("ts_id")
                        if ts_id and role != "viewer":
                            self.ws_manager.active_editors.setdefault(ts_id, {})[username] = 1.0
                            await self.ws_manager.broadcast_json(
                                {
                                    "type": "FOCUS_UPDATE",
                                    "data": {"ts_id": ts_id, "user": username, "status": "editing"},
                                }
                            )
                            self.signals.focus_changed.emit(ts_id, username)

                    elif action == "blur":
                        ts_id = data.get("ts_id")
                        if ts_id:
                            self.ws_manager.active_editors.get(ts_id, {}).pop(username, None)
                            await self.ws_manager.broadcast_json(
                                {"type": "FOCUS_UPDATE", "data": {"ts_id": ts_id, "user": username, "status": "idle"}}
                            )

                    elif action == "chat":
                        from datetime import datetime

                        message_text = data.get("message", "").strip()
                        if message_text:
                            await self.ws_manager.broadcast_json(
                                {
                                    "type": "CHAT_MESSAGE",
                                    "data": {
                                        "user": username,
                                        "role": role,
                                        "text": message_text,
                                        "time": datetime.now().isoformat(),
                                    },
                                }
                            )

            except WebSocketDisconnect:
                departed_info = self.ws_manager.disconnect(websocket)
                if departed_info:
                    departed_user = departed_info["name"]
                    self.ws_manager.cleanup_user_editors(departed_user)
                    await self.ws_manager.broadcast_json(
                        {
                            "type": "USER_DISCONNECTED",
                            "data": {
                                "user": departed_user,
                                "online_users": self.ws_manager.get_online_users(),
                            },
                        }
                    )

        # ── i18n ───────────────────────────────────────────────────────────────

        @app.get("/api/v1/i18n")
        async def get_i18n(user: dict = Depends(self._verify_session)):
            keys = [
                "Original",
                "Translation",
                "Search",
                "Refresh",
                "Status",
                "Reviewed",
                "Fuzzy",
                "Untranslated",
                "Save Success",
                "Save Failed",
                "Project Info",
                "Access Token",
                "Login",
                "Logout",
                "Need Authentication",
                "Enter Access Token",
                "Connect to Host",
                "Form",
                "Singular",
                "Plural",
                "Search source, translation, comment...",
                "No Data",
                "Syncing to host...",
                "Sync failed",
                "Invalid Token",
                "Cannot connect to host",
                "Someone is editing...",
                "All",
                "Translated",
                "Ignored",
                "entries",
                "of",
                "page",
                "Back to top",
                "Light Mode",
                "Dark Mode",
                "Keyboard Shortcuts",
                "Connected",
                "Disconnected",
                "Reconnecting",
                "Connection failed",
                "Saved",
                "Save failed",
                "Source copied to translation",
                "Status updated",
                "Invalid or expired token",
                "is editing",
                "online",
                "No matching entries",
                "No entries available",
                "Display name for collaboration",
                "Progress",
                "reviewed",
                "translated",
                "fuzzy",
                "untranslated",
                "Prev",
                "Next",
                "rows",
                "Go to page",
                "is editing...",
                "AI Translate",
                "Chat",
                "Send",
                "Type a message...",
                "Admin",
                "Reviewer",
                "Translator",
                "Viewer",
                "Permission Denied",
                "Account Login",
                "Token Login",
                "Username",
                "Password",
                "Remember Me",
            ]
            return {k: _(k) for k in keys}

        # ── Data Endpoints ─────────────────────────────────────────────────────

        @app.get("/api/v1/project")
        async def get_project(user: dict = Depends(self._verify_session)):
            main_app = self._get_main_app()
            items = main_app.translatable_objects
            total = len(items)
            reviewed = sum(1 for ts in items if ts.is_reviewed)
            fuzzy = sum(1 for ts in items if ts.is_fuzzy and not ts.is_reviewed)
            translated = sum(1 for ts in items if ts.translation and not ts.is_reviewed and not ts.is_fuzzy)
            untranslated = total - reviewed - fuzzy - translated
            project_name = "LexiSync"
            if main_app.is_project_mode:
                project_name = main_app.project_config.get("name", "Unnamed Project")
            elif main_app.current_file_path:
                project_name = os.path.basename(main_app.current_file_path)

            return {
                "name": project_name,
                "source_lang": main_app.source_language,
                "target_lang": main_app.current_target_language,
                "total": total,
                "reviewed": reviewed,
                "fuzzy": fuzzy,
                "translated": translated,
                "untranslated": untranslated,
            }

        @app.get("/api/v1/strings")
        async def get_strings(
            page: int = 1,
            page_size: int = 50,
            search: str | None = None,
            status: str | None = None,
            user: dict = Depends(self._verify_session),
        ):
            main_app = self._get_main_app()
            data = list(main_app.translatable_objects)

            if search:
                q = search.lower()
                data = [ts for ts in data if q in ts._search_cache]

            data = self._apply_status_filter(data, status)

            total = len(data)
            start = (page - 1) * page_size
            end = start + page_size

            items = []
            for ts in data[start:end]:
                items.append(
                    {
                        "id": ts.id,
                        "source": ts.original_semantic,
                        "translation": ts.translation,
                        "is_plural": ts.is_plural,
                        "plural_translations": ts.plural_translations,
                        "comment": ts.comment,
                        "is_reviewed": ts.is_reviewed,
                        "is_fuzzy": ts.is_fuzzy,
                        "active_editors": list(self.ws_manager.active_editors.get(ts.id, {}).keys()),
                    }
                )
            return {"items": items, "total": total}

        @app.post("/api/v1/update")
        async def update(data: TranslationUpdate, user: dict = Depends(self._verify_session)):
            role = user["role"]
            if role == "viewer":
                raise HTTPException(status_code=403, detail="Viewers cannot edit.")
            if data.is_reviewed is not None and role == "translator":
                raise HTTPException(status_code=403, detail="Translators cannot mark as reviewed.")

            data.user = user["name"]
            self.signals.update_requested.emit(data)
            return {"status": "ok"}

        @app.post("/api/v1/ai-translate")
        async def ai_translate(req: AITranslateRequest, user: dict = Depends(self._verify_session)):
            if user["role"] == "viewer":
                raise HTTPException(status_code=403, detail="Viewers cannot use AI translation.")
            self.signals.ai_translate_requested.emit(req.ts_id)
            return {"status": "ok"}

        @app.get("/api/v1/users")
        async def get_users(user: dict = Depends(self._verify_session)):
            return {"users": self.ws_manager.get_online_users()}

        @app.get("/api/v1/locate")
        async def locate(
            ts_id: str,
            status: str | None = None,
            search: str | None = None,
            page_size: int = 50,
            user: dict = Depends(self._verify_session),
        ):
            main_app = self._get_main_app()
            data = list(main_app.translatable_objects)
            if search:
                q = search.lower()
                data = [ts for ts in data if q in ts._search_cache]
            data = self._apply_status_filter(data, status)
            for idx, ts in enumerate(data):
                if ts.id == ts_id:
                    return {
                        "found": True,
                        "page": idx // page_size + 1,
                        "index": idx,
                        "total_pages": (len(data) + page_size - 1) // page_size,
                    }
            return {"found": False, "page": None, "index": None}

        # ── Static Files ───────────────────────────────────────────────────────
        web_path = get_resource_path("resources/web")
        if os.path.exists(web_path):
            assets_path = os.path.join(web_path, "assets")
            if os.path.exists(assets_path):
                app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

            @app.get("/")
            async def index():
                return FileResponse(os.path.join(web_path, "index.html"))

            app.mount("/", StaticFiles(directory=web_path), name="web_root")

    def broadcast_data_change(
        self,
        ts_id: str,
        new_text: str | None = None,
        is_reviewed: bool | None = None,
        is_fuzzy: bool | None = None,
        plural_index: int = 0,
        user: str = "Host",
    ):
        if not self.is_running or not self.loop or not self.ws_manager.active_connections:
            return
        payload = {
            "type": "DATA_UPDATE",
            "data": {
                "ts_id": ts_id,
                "new_text": new_text,
                "is_reviewed": is_reviewed,
                "is_fuzzy": is_fuzzy,
                "plural_index": plural_index,
                "user": user,
            },
        }
        asyncio.run_coroutine_threadsafe(self.ws_manager.broadcast_json(payload), self.loop)

    def run(self):
        self.is_running = True
        config = uvicorn.Config(self.fastapi_app, host=self.host, port=self.port, log_level="warning", loop="asyncio")
        self.server = uvicorn.Server(config)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "127.0.0.1"
        self.signals.server_started.emit(f"http://{ip}:{self.port}")
        self.server.run()

    def stop(self):
        if hasattr(self, "server"):
            self.server.should_exit = True
        self.is_running = False

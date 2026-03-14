# --- START OF FILE web_server_service.py ---
# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import asyncio
import collections
from datetime import datetime
import hashlib
import logging
import os
import socket
import time
import uuid
import weakref

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PySide6.QtCore import QObject, QThread, Signal
import uvicorn

from lexisync.services.permissions import (
    get_effective_permissions,
    get_effective_scope,
    scope_allows_file,
    scope_allows_language,
)
from lexisync.services.tunnel import TunnelManager
from lexisync.utils.localization import _
from lexisync.utils.path_utils import get_resource_path

logger = logging.getLogger(__name__)

MAX_AUDIT_ENTRIES = 2000
FOCUS_LOCK_TIMEOUT = 120.0
FOCUS_CLEANUP_INTERVAL = 30.0

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


# ─── Audit Log ─────────────────────────────────────────────────────────────────


class AuditLog:
    def __init__(self, maxlen: int = MAX_AUDIT_ENTRIES):
        self._entries: collections.deque[dict] = collections.deque(maxlen=maxlen)

    def record(
        self,
        user: str,
        action: str,
        ts_id: str | None = None,
        old_value: str | None = None,
        new_value: str | None = None,
        ip: str = "",
        extra: dict | None = None,
    ) -> dict:
        entry: dict = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "user": user,
            "action": action,
            "ts_id": ts_id,
            "old_value": old_value,
            "new_value": new_value,
            "ip": ip,
        }
        if extra:
            entry.update(extra)
        self._entries.appendleft(entry)
        return entry

    def get_entries(self, limit: int = 200, user: str | None = None, action: str | None = None) -> list[dict]:
        result = list(self._entries)
        if user:
            result = [e for e in result if e["user"] == user]
        if action:
            result = [e for e in result if e["action"] == action]
        return result[:limit]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


# ─── Connection Manager ────────────────────────────────────────────────────────


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.active_editors: dict[str, dict[str, float]] = {}
        self._ws_user: dict[int, dict] = {}

    def disconnect(self, websocket: WebSocket) -> dict | None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        return self._ws_user.pop(id(websocket), None)

    def get_online_users(self) -> list[dict]:
        seen: dict[str, dict] = {}
        for info in self._ws_user.values():
            seen[info["name"]] = {"name": info["name"], "role": info["role"]}
        return list(seen.values())

    def cleanup_user_editors(self, username: str) -> list[str]:
        affected = []
        for ts_id, editors in list(self.active_editors.items()):
            if username in editors:
                editors.pop(username, None)
                affected.append(ts_id)
            if not editors:
                del self.active_editors[ts_id]
        return affected

    async def broadcast_json(self, message: dict) -> None:
        if not self.active_connections:
            return

        async def send_to_client(ws: WebSocket):
            try:
                async with asyncio.timeout(3.0):
                    await ws.send_json(message)
                return None
            except Exception as e:
                logger.debug(f"Failed to send to a client, marking as dead: {e}")
                return ws

        tasks = [send_to_client(ws) for ws in self.active_connections]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        dead_connections = [res for res in results if isinstance(res, WebSocket)]
        for ws in dead_connections:
            self.disconnect(ws)


# ─── Qt Signals ────────────────────────────────────────────────────────────────


class WebServerSignals(QObject):
    update_requested = Signal(object)
    focus_changed = Signal(str, str)
    server_started = Signal(str)
    server_stopped = Signal()
    ai_translate_requested = Signal(str)
    approval_requested = Signal(str, str, str)


# ─── Web Server Service ────────────────────────────────────────────────────────


class WebServerService(QThread):
    def __init__(self, app_instance):
        super().__init__()
        self.app_ref = weakref.ref(app_instance)
        self.signals = WebServerSignals()
        self.port = 20455
        self.host = "0.0.0.0"
        self.is_running = False
        self.loop: asyncio.AbstractEventLoop | None = None

        self.sessions: dict[str, dict] = {}

        self.require_approval = app_instance.config.get("cloud_require_approval", True)
        self.approved_ips: set[str] = set()
        self.pending_approvals: dict[str, asyncio.Event] = {}
        self.approval_results: dict[str, bool] = {}

        self.tunnel_manager = TunnelManager()
        self.audit_log = AuditLog()

        self.update_auth_data(
            app_instance.config.get("cloud_users", []),
            app_instance.config.get("cloud_tokens", []),
            app_instance.config.get("cloud_groups", []),
        )

        self.ws_manager = ConnectionManager()
        self.fastapi_app = FastAPI()
        self.fastapi_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
        self._setup_routes()

    def update_auth_data(self, users: list, tokens: list, groups: list | None = None) -> None:
        self.cloud_users = users
        self.cloud_tokens = tokens
        self.cloud_groups = groups or []

    def resolve_approval(self, req_id: str, approved: bool) -> None:
        if req_id in self.pending_approvals:
            self.approval_results[req_id] = approved
            self.pending_approvals[req_id].set()

    def _verify_session(self, request: Request) -> dict:
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

        if not token:
            token = request.query_params.get("token")

        if not token or token not in self.sessions:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        return self.sessions[token]

    def _get_main_app(self):
        app = self.app_ref()
        if not app:
            raise HTTPException(status_code=503, detail="Application unavailable")
        return app

    def _require(self, session: dict, perm: str) -> None:
        if perm not in get_effective_permissions(session, self.cloud_groups):
            raise HTTPException(status_code=403, detail=f"Permission denied: {perm}")

    def _get_client_ip(self, request: Request) -> str:
        raw = (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Forwarded-For")
            or (request.client.host if request.client else "unknown")
        )
        return raw.split(",")[0].strip()

    def _build_user_session(self, user_data: dict) -> dict:
        return {
            "name": user_data["username"],
            "role": user_data["role"],
            "groups": user_data.get("groups", []),
            "custom_permissions": user_data.get("custom_permissions") or {},
            "scope": user_data.get("scope"),
            "token_permissions": None,
        }

    def _build_token_session(self, display_name: str, token_data: dict) -> dict:
        return {
            "name": display_name,
            "role": token_data["role"],
            "groups": [],
            "custom_permissions": {},
            "scope": token_data.get("scope"),
            "token_permissions": token_data.get("permissions"),
            "_token_value": token_data["token"],
        }

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

    async def _check_approval(self, request: Request, context_info: str) -> None:
        if not self.require_approval:
            return
        ip = self._get_client_ip(request)
        if ip in ("127.0.0.1", "::1", "localhost") or ip in self.approved_ips:
            return
        req_id = str(uuid.uuid4())
        event = asyncio.Event()
        self.pending_approvals[req_id] = event
        self.signals.approval_requested.emit(req_id, ip, context_info)
        try:
            await asyncio.wait_for(event.wait(), timeout=60.0)
        except TimeoutError as e:
            self.pending_approvals.pop(req_id, None)
            raise HTTPException(status_code=403, detail="Approval request timed out.") from e
        if not self.approval_results.pop(req_id, False):
            raise HTTPException(status_code=403, detail="Connection rejected by host.")
        self.approved_ips.add(ip)

    async def _focus_cleanup_loop(self) -> None:
        while self.is_running:
            await asyncio.sleep(FOCUS_CLEANUP_INTERVAL)
            now = time.time()
            for ts_id in list(self.ws_manager.active_editors):
                editors = self.ws_manager.active_editors.get(ts_id)
                if not editors:
                    continue
                stale_users = [u for u, ts in list(editors.items()) if now - ts > FOCUS_LOCK_TIMEOUT]
                for username in stale_users:
                    editors.pop(username, None)
                    await self.ws_manager.broadcast_json(
                        {"type": "FOCUS_UPDATE", "data": {"ts_id": ts_id, "user": username, "status": "idle"}}
                    )
                if not editors:
                    self.ws_manager.active_editors.pop(ts_id, None)

    def _setup_routes(self) -> None:
        app = self.fastapi_app

        @app.on_event("startup")
        async def _startup():
            self.loop = asyncio.get_running_loop()
            asyncio.create_task(self._focus_cleanup_loop())

        @app.post("/api/v1/login")
        async def login_account(req: LoginRequest, request: Request):
            await self._check_approval(request, f"Account login: {req.username}")
            for u in self.cloud_users:
                if u["username"] == req.username and verify_password(req.password, u["password_hash"]):
                    sid = str(uuid.uuid4())
                    session = self._build_user_session(u)
                    self.sessions[sid] = session
                    self.audit_log.record(
                        user=u["username"], action="login", ip=self._get_client_ip(request), extra={"method": "account"}
                    )

                    main_app = self._get_main_app()
                    remember_token = f"{u['username']}:{main_app.cloud_token}"

                    return {
                        "token": sid,
                        "name": session["name"],
                        "role": session["role"],
                        "remember_token": remember_token,
                    }
            raise HTTPException(status_code=401, detail="Invalid username or password")

        @app.post("/api/v1/login-remembered")
        async def login_remembered(req: RememberMeLoginRequest, request: Request):
            await self._check_approval(request, "Auto-login attempt")
            try:
                username, host_token = req.remember_token.split(":", 1)
            except (ValueError, AttributeError) as e:
                raise HTTPException(status_code=400, detail="Invalid remember_token format") from e
            main_app = self._get_main_app()
            if host_token != main_app.cloud_token:
                raise HTTPException(status_code=401, detail="Host has been restarted or token is invalid")
            user_data = next((u for u in self.cloud_users if u["username"] == username), None)
            if not user_data:
                raise HTTPException(status_code=401, detail="User not found")
            sid = str(uuid.uuid4())
            session = self._build_user_session(user_data)
            self.sessions[sid] = session
            return {"token": sid, "name": session["name"], "role": session["role"]}

        @app.post("/api/v1/login-token")
        async def login_token(req: TokenLoginRequest, request: Request):
            await self._check_approval(request, f"Token login: {req.display_name}")
            client_ip = self._get_client_ip(request)
            current_time = time.time()

            for t in self.cloud_tokens:
                if t["token"] != req.token:
                    continue
                if t.get("expires_at") and current_time > t["expires_at"]:
                    raise HTTPException(status_code=401, detail="Token has expired")

                ip_whitelist = t.get("ip_whitelist")
                if ip_whitelist:
                    import fnmatch as _fnm

                    if not any(_fnm.fnmatch(client_ip, pat) for pat in ip_whitelist):
                        raise HTTPException(status_code=403, detail="Access denied: IP not whitelisted")

                max_uses = t.get("max_uses")
                use_count = t.get("use_count", 0)
                if max_uses and max_uses > 0:
                    if use_count >= max_uses:
                        raise HTTPException(status_code=403, detail="Token usage limit reached")
                    t["use_count"] = use_count + 1

                display_name = req.display_name.strip() or "Guest"
                sid = str(uuid.uuid4())
                session = self._build_token_session(display_name, t)
                self.sessions[sid] = session
                return {"token": sid, "name": display_name, "role": session["role"]}
            raise HTTPException(status_code=401, detail="Invalid access token")

        @app.get("/api/v1/me")
        async def get_me(session: dict = Depends(self._verify_session)):
            perms = list(get_effective_permissions(session, self.cloud_groups))
            scope = get_effective_scope(session, self.cloud_groups)
            return {"name": session["name"], "role": session["role"], "permissions": perms, "scope": scope}

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket, token: str | None = None):
            await websocket.accept()
            if not token or token not in self.sessions:
                await websocket.close(code=1008)
                return

            session = self.sessions[token]
            username = session["name"]
            role = session["role"]
            perms = get_effective_permissions(session, self.cloud_groups)

            self.ws_manager.active_connections.append(websocket)
            self.ws_manager._ws_user[id(websocket)] = session

            await self.ws_manager.broadcast_json(
                {
                    "type": "USER_CONNECTED",
                    "data": {"user": username, "role": role, "online_users": self.ws_manager.get_online_users()},
                }
            )

            try:
                while True:
                    data = await websocket.receive_json()
                    action = data.get("action")

                    if action == "ai_start" and "ai_translate" in perms:
                        ts_id = data.get("ts_id")
                        if ts_id:
                            await self.ws_manager.broadcast_json(
                                {
                                    "type": "AI_STATUS_UPDATE",
                                    "data": {"ts_id": ts_id, "status": "loading", "user": username},
                                }
                            )
                            self.signals.ai_translate_requested.emit(ts_id)

                    elif action == "focus" and "translate" in perms:
                        ts_id = data.get("ts_id")
                        if ts_id:
                            self.ws_manager.active_editors.setdefault(ts_id, {})[username] = time.time()
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

                    elif action == "chat" and "chat" in perms:
                        msg = data.get("message", "").strip()
                        if msg:
                            await self.ws_manager.broadcast_json(
                                {
                                    "type": "CHAT_MESSAGE",
                                    "data": {
                                        "user": username,
                                        "role": role,
                                        "text": msg,
                                        "time": datetime.now().isoformat(),
                                    },
                                }
                            )

            except WebSocketDisconnect:
                departed = self.ws_manager.disconnect(websocket)
                if departed:
                    self.ws_manager.cleanup_user_editors(departed["name"])
                    await self.ws_manager.broadcast_json(
                        {
                            "type": "USER_DISCONNECTED",
                            "data": {"user": departed["name"], "online_users": self.ws_manager.get_online_users()},
                        }
                    )

        @app.get("/api/v1/i18n")
        async def get_i18n(session: dict = Depends(self._verify_session)):
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
                "No chat permission",
                "Scoped",
                "Restricted scope",
                "Languages",
                "Files",
                "Host state changed. Refreshing...",
            ]
            return {k: _(k) for k in keys}

        @app.get("/api/v1/project")
        async def get_project(session: dict = Depends(self._verify_session)):
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
            session: dict = Depends(self._verify_session),
        ):
            main_app = self._get_main_app()
            scope = get_effective_scope(session, self.cloud_groups)
            target_lang = main_app.current_target_language
            if not scope_allows_language(scope, target_lang):
                return {"items": [], "total": 0}
            current_file = os.path.basename(main_app.current_file_path or "")
            if scope.get("files") and not scope_allows_file(scope, current_file):
                return {"items": [], "total": 0}

            data = list(main_app.translatable_objects)
            if search:
                q = search.lower()
                data = [ts for ts in data if q in ts._search_cache]
            data = self._apply_status_filter(data, status)
            total = len(data)

            if (page - 1) * page_size >= total:
                page = 1

            start = (page - 1) * page_size

            items = []
            for ts in data[start : start + page_size]:
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
        async def update(data: TranslationUpdate, request: Request, session: dict = Depends(self._verify_session)):
            if data.new_text is not None:
                self._require(session, "translate")
            if data.is_reviewed is True:
                self._require(session, "review")
            if data.is_fuzzy is not None:
                self._require(session, "fuzzy")

            main_app = self._get_main_app()
            scope = get_effective_scope(session, self.cloud_groups)
            if not scope_allows_language(scope, main_app.current_target_language):
                raise HTTPException(status_code=403, detail="Language not in your permitted scope")

            data.user = session["name"]
            self.signals.update_requested.emit(data)
            return {"status": "ok"}

        @app.post("/api/v1/ai-translate")
        async def ai_translate(req: AITranslateRequest, session: dict = Depends(self._verify_session)):
            self._require(session, "ai_translate")
            await self.ws_manager.broadcast_json(
                {"type": "AI_STATUS_UPDATE", "data": {"ts_id": req.ts_id, "status": "loading", "user": session["name"]}}
            )
            self.signals.ai_translate_requested.emit(req.ts_id)
            return {"status": "accepted"}

        @app.get("/api/v1/users")
        async def get_users(session: dict = Depends(self._verify_session)):
            return {"users": self.ws_manager.get_online_users()}

        web_path = get_resource_path("resources/web")
        if os.path.exists(web_path):
            assets_path = os.path.join(web_path, "assets")
            if os.path.exists(assets_path):
                app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

            @app.get("/")
            async def index():
                return FileResponse(os.path.join(web_path, "index.html"))

            app.mount("/", StaticFiles(directory=web_path), name="web_root")

    def _run_async(self, coro) -> None:
        if self.is_running and self.loop and self.ws_manager.active_connections:
            asyncio.run_coroutine_threadsafe(coro, self.loop)

    def broadcast_bulk_data_change(self, changes: list[dict], user: str = "Host") -> None:
        if not changes:
            return
        self._run_async(
            self.ws_manager.broadcast_json({"type": "BULK_DATA_UPDATE", "data": {"user": user, "changes": changes}})
        )

    def broadcast_data_change(
        self,
        ts_id: str,
        new_text: str | None = None,
        is_reviewed: bool | None = None,
        is_fuzzy: bool | None = None,
        plural_index: int = 0,
        user: str = "Host",
    ) -> None:
        change_item = {
            "ts_id": ts_id,
            "new_text": new_text,
            "is_reviewed": is_reviewed,
            "is_fuzzy": is_fuzzy,
            "plural_index": plural_index,
        }
        self.broadcast_bulk_data_change([change_item], user)

    def broadcast_ai_status(self, ts_id: str, status: str, user: str = "AI") -> None:
        self._run_async(
            self.ws_manager.broadcast_json(
                {"type": "AI_STATUS_UPDATE", "data": {"ts_id": ts_id, "status": status, "user": user}}
            )
        )

    def broadcast_force_blur(self, ts_id: str, initiator: str = "System") -> None:
        self.ws_manager.active_editors.pop(ts_id, None)
        self._run_async(
            self.ws_manager.broadcast_json({"type": "FORCE_BLUR", "data": {"ts_id": ts_id, "initiator": initiator}})
        )

    def broadcast_host_state_changed(self) -> None:
        """广播主机状态改变（切换文件、切换语言等），要求前端刷新"""
        self._run_async(self.ws_manager.broadcast_json({"type": "HOST_STATE_CHANGED", "data": {}}))

    def run(self) -> None:
        self.is_running = True
        config = uvicorn.Config(self.fastapi_app, host=self.host, port=self.port, log_level="warning", loop="asyncio")
        self.server = uvicorn.Server(config)

        ip = "127.0.0.1"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            temp_ip = s.getsockname()[0]
            s.close()
            if temp_ip.startswith("198.18.") or temp_ip.startswith("127."):
                import psutil

                for _iface, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if addr.family == socket.AF_INET and addr.address.startswith(("192.168.", "172.", "10.")):
                            ip = addr.address
                            break
                    if ip != "127.0.0.1":
                        break
            else:
                ip = temp_ip
        except Exception:
            pass

        self.signals.server_started.emit(f"http://{ip}:{self.port}")

        app_config = self._get_main_app().config
        tunnel_cfg = app_config.get("tunnel_settings", {})
        if tunnel_cfg.get("active"):
            provider = tunnel_cfg.get("provider", "cloudflare")
            self.tunnel_manager.start_tunnel(provider, self.port, tunnel_cfg.get(provider, {}))

        self.server.run()

    def stop(self) -> None:
        self.is_running = False
        self.tunnel_manager.stop_tunnel()
        if hasattr(self, "server"):
            self.server.should_exit = True


# --- END OF FILE web_server_service.py ---

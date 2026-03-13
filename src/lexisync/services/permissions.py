# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import fnmatch

# ─── Permission Registry ──────────────────────────────────────────────────────

ALL_PERMISSIONS: dict[str, str] = {
    "translate": "Edit Translations",
    "review": "Mark as Reviewed",
    "fuzzy": "Mark as Fuzzy",
    "ai_translate": "Use AI Translation",
    "chat": "Use Chat",
    "export": "Export Files",
    "view_audit": "View Audit Logs",
    "manage_users": "Manage Users",
    "manage_tokens": "Manage Tokens",
    "manage_groups": "Manage Groups",
}

# Default permissions
DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": set(ALL_PERMISSIONS.keys()),
    "reviewer": {"translate", "review", "fuzzy", "ai_translate", "chat"},
    "translator": {"translate", "fuzzy", "ai_translate", "chat"},
    "viewer": {"chat"},
}


# ─── Permission Resolution ────────────────────────────────────────────────────


def get_effective_permissions(session: dict, groups: list[dict]) -> frozenset[str]:
    """
    Compute the final permission set for a session.

    Priority chain (highest → lowest):
      1. token_permissions  — if the token explicitly lists permissions, use those as baseline
         instead of role defaults (allows issuing a highly restricted token regardless of role)
      2. role defaults      — used when no token_permissions override is present
      3. group permissions  — unioned on top of role defaults
      4. custom grants      — per-user extra grants (always applied last)
      5. custom revokes     — per-user explicit removals (always applied last)
    """
    if session.get("token_permissions") is not None:
        # Token carries its own explicit permission set → ignore role defaults
        perms: set[str] = set(session["token_permissions"])
    else:
        role = session.get("role", "viewer")
        perms = set(DEFAULT_ROLE_PERMISSIONS.get(role, set()))

        # Union in every group this session belongs to
        session_groups = set(session.get("groups", []))
        for g in groups:
            if g["id"] in session_groups:
                perms.update(g.get("permissions", []))

    # Per-session custom overrides (always respected regardless of token/role/group)
    custom = session.get("custom_permissions") or {}
    perms.update(custom.get("grant", []))
    perms.difference_update(custom.get("revoke", []))

    return frozenset(perms)


def has_permission(session: dict, groups: list[dict], perm: str) -> bool:
    return perm in get_effective_permissions(session, groups)


# ─── Scope Resolution ─────────────────────────────────────────────────────────


def get_effective_scope(session: dict, groups: list[dict]) -> dict:
    """
    计算最终的作用域限制。
    返回 {"languages": list|None, "files": list|None}。
    None 表示无限制（允许所有）。
    """
    if session.get("role") == "admin":
        return {"languages": None, "files": None}

    scope = session.get("scope")
    if scope is not None:
        return {
            "languages": scope.get("languages"),
            "files": scope.get("files"),
        }

    # 3. 合并组范围
    session_groups = set(session.get("groups", []))

    merged_langs: set[str] | None = None
    merged_files: set[str] | None = None
    has_group_with_restriction = False

    for g in groups:
        if g["id"] not in session_groups:
            continue

        g_scope = g.get("scope") or {}
        g_langs = g_scope.get("languages")
        g_files = g_scope.get("files")

        # 处理语言轴
        if g_langs is not None:
            if merged_langs is None:
                merged_langs = set()
            merged_langs.update(g_langs)
            has_group_with_restriction = True

        # 处理文件轴
        if g_files is not None:
            if merged_files is None:
                merged_files = set()
            merged_files.update(g_files)
            has_group_with_restriction = True

    return {
        "languages": list(merged_langs) if merged_langs is not None else None,
        "files": list(merged_files) if merged_files is not None else None,
    }


def scope_allows_language(scope: dict, language: str) -> bool:
    langs = scope.get("languages")
    return langs is None or language in langs


def scope_allows_file(scope: dict, filename: str) -> bool:
    """Supports glob patterns, e.g. ``*.po``, ``messages.*``."""
    patterns = scope.get("files")
    if patterns is None:
        return True
    return any(fnmatch.fnmatch(filename, pat) for pat in patterns)

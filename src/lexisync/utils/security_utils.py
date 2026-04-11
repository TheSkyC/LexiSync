# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import base64
import hashlib
import hmac
import logging
import os
from pathlib import Path
import platform
import sys
import threading

from lexisync.utils.localization import _
from lexisync.utils.path_utils import get_app_data_path

logger = logging.getLogger(__name__)

ENCRYPTION_PREFIX = "ENC:"
SECRET_FILE = "secret.key"
KEYRING_SERVICE = "LexiSync"
KEYRING_USER = "master_key"

COLOR_WARN = "\033[93m"  # Yellow
COLOR_RESET = "\033[0m"  # Reset

_key_lock = threading.Lock()
_keyring_init_lock = threading.Lock()
_keyring_state = {"module": None, "ready": False}

_HKDF_INFO = b"lexisync-enc\x00"
_PAD_BLOCK = 64


def _ensure_keyring():
    """Import keyring lazily and pin the platform backend at most once per process."""
    if _keyring_state["ready"]:
        return _keyring_state["module"]

    with _keyring_init_lock:
        if _keyring_state["ready"]:
            return _keyring_state["module"]

        import keyring as _kr
        import keyring.errors  # noqa: F401

        try:
            system = platform.system()
            if system == "Windows":
                from keyring.backends.Windows import WinVaultKeyring

                _kr.set_keyring(WinVaultKeyring())
            elif system == "Darwin":
                from keyring.backends.macOS import Keyring

                _kr.set_keyring(Keyring())
        except Exception as e:
            logger.debug("Explicit keyring init failed, falling back to auto-scan: %s", e)

        _keyring_state["module"] = _kr
        _keyring_state["ready"] = True

    return _keyring_state["module"]


def _pad(data: bytes) -> bytes:
    padding_len = _PAD_BLOCK - (len(data) % _PAD_BLOCK)
    return data + bytes([padding_len] * padding_len)


def _unpad(data: bytes) -> bytes:
    if not data:
        raise ValueError("empty payload")

    padding_len = data[-1]
    if padding_len < 1 or padding_len > _PAD_BLOCK or data[-padding_len:] != bytes([padding_len] * padding_len):
        raise ValueError("invalid padding")

    return data[:-padding_len]


def _hkdf_expand(prk: bytes, length: int) -> bytes:
    if length > 255 * 32:
        raise ValueError(f"HKDF-Expand: requested length {length} exceeds maximum 8160 bytes")

    output = b""
    block = b""
    counter = 1
    while len(output) < length:
        block = hmac.new(prk, block + _HKDF_INFO + bytes([counter]), hashlib.sha256).digest()
        output += block
        counter += 1
    return output[:length]


def _derive_keystream(master_key: bytes, salt: bytes, length: int) -> bytes:
    prk = hmac.new(salt, master_key, hashlib.sha256).digest()
    return _hkdf_expand(prk, length)


def _set_win32_owner_only(path: Path) -> None:
    """Restrict file access to the current user only on Windows."""
    try:
        import importlib

        win32api = importlib.import_module("win32api")
        win32security = importlib.import_module("win32security")

        security_descriptor = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION)
        dacl = win32security.ACL()
        user_sid = win32security.GetTokenInformation(
            win32security.OpenProcessToken(win32api.GetCurrentProcess(), 0x0008),
            win32security.TokenUser,
        )[0]
        dacl.AddAccessAllowedAce(win32security.ACL_REVISION, 0x1F01FF, user_sid)
        security_descriptor.SetSecurityDescriptorDacl(True, dacl, False)
        win32security.SetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION, security_descriptor)
    except ImportError:
        logger.debug("pywin32 not available; skipping ACL restriction for %s", path)
    except Exception as e:
        logger.warning("Failed to set ACL on %s: %s", path, e)


def _get_or_create_master_key() -> bytes:
    """
    获取主密钥。
    策略：
    1. 尝试从系统 Keyring 获取。
    2. 如果 Keyring 不可用或为空，尝试从本地 secret.key 文件获取（回退机制）。
    3. 如果都不存在，生成新密钥。
    4. 保存时，优先存入 Keyring；如果失败，则存入本地文件。
    """
    with _key_lock:
        keyring_module = _ensure_keyring()

        try:
            key_hex = keyring_module.get_password(KEYRING_SERVICE, KEYRING_USER)
            if key_hex:
                return bytes.fromhex(key_hex)
        except Exception as e:
            logger.warning("Keyring lookup failed (will try local file): %s", e)

        key_path = Path(get_app_data_path()) / SECRET_FILE
        key: bytes | None = None

        if key_path.exists():
            try:
                data = key_path.read_bytes()
                if len(data) == 32:
                    key = data
                    logger.info("Loaded master key from local file (fallback).")
            except Exception as e:
                logger.error("Failed to read local key file: %s", e)

        if not key:
            logger.info("Generating new master key.")
            key = os.urandom(32)

        saved_to_keyring = False
        try:
            keyring_module.set_password(KEYRING_SERVICE, KEYRING_USER, key.hex())
            saved_to_keyring = True
            logger.info("Master key saved to system Keyring.")
        except Exception as e:
            logger.error("Failed to save key to Keyring: %s", e)

        if not saved_to_keyring:
            try:
                key_path.write_bytes(key)
                if sys.platform == "win32":
                    _set_win32_owner_only(key_path)
                else:
                    key_path.chmod(0o600)
                logger.warning(
                    "%s[SECURITY WARNING] Master key saved to UNENCRYPTED local file (Keyring unavailable): %s%s",
                    COLOR_WARN,
                    key_path,
                    COLOR_RESET,
                )
            except Exception as e:
                error_message = _(
                    "Critical Security Error: Could not save master key to Keyring OR local file.\n"
                    "Path: {path}\n"
                    "Error: {error}"
                ).format(path=key_path, error=str(e))
                raise OSError(error_message) from e

        return key


def encrypt_text(text: str) -> str:
    """
    Encrypt plaintext and return ciphertext in ENC:<base64> format.

    v1 payload: [0x01 version][16B salt][32B HMAC][N bytes ciphertext]
    """
    if not text:
        return ""

    try:
        master_key = _get_or_create_master_key()

        text_bytes = _pad(text.encode("utf-8"))
        salt = os.urandom(16)

        keystream = _derive_keystream(master_key, salt, len(text_bytes))
        encrypted_bytes = bytes(a ^ b for a, b in zip(text_bytes, keystream, strict=False))
        signature = hmac.new(master_key, salt + encrypted_bytes, hashlib.sha256).digest()

        payload = b"\x01" + salt + signature + encrypted_bytes

        return ENCRYPTION_PREFIX + base64.b64encode(payload).decode("utf-8")
    except Exception as e:
        logger.error("Encryption failed: %s", e)
        return ""


def _try_decrypt_hkdf(payload: bytes, master_key: bytes) -> str | None:
    if len(payload) < 49:
        return None

    salt = payload[1:17]
    signature = payload[17:49]
    encrypted_bytes = payload[49:]
    expected_signature = hmac.new(master_key, salt + encrypted_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    keystream = _derive_keystream(master_key, salt, len(encrypted_bytes))
    decrypted_bytes = bytes(a ^ b for a, b in zip(encrypted_bytes, keystream, strict=False))

    try:
        return _unpad(decrypted_bytes).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def _try_decrypt_legacy(payload: bytes, master_key: bytes) -> str | None:
    if len(payload) < 48:
        return None

    salt = payload[:16]
    signature = payload[16:48]
    encrypted_bytes = payload[48:]

    expected_signature = hmac.new(master_key, salt + encrypted_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    keystream = hashlib.shake_256(master_key + salt).digest(len(encrypted_bytes))
    try:
        return bytes(a ^ b for a, b in zip(encrypted_bytes, keystream, strict=False)).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def decrypt_text(text: str) -> str:
    """
    Decrypt ENC:<base64> ciphertext and preserve plaintext input for migration compatibility.

    Supports both v1 HKDF payloads and legacy v0 SHAKE-256 payloads.
    """
    if not text or not text.startswith(ENCRYPTION_PREFIX):
        return text

    try:
        master_key = _get_or_create_master_key()

        try:
            payload = base64.b64decode(text[len(ENCRYPTION_PREFIX) :])
        except Exception:
            return ""

        if len(payload) < 1:
            return ""

        if payload[0] == 0x01:
            result = _try_decrypt_hkdf(payload, master_key)
            if result is None:
                result = _try_decrypt_legacy(payload, master_key)
            if result is None:
                logger.warning("Decryption signature mismatch — data may be tampered.")
            return result or ""

        result = _try_decrypt_legacy(payload, master_key)
        if result is None:
            logger.warning("Decryption signature mismatch — data may be tampered.")
        return result or ""
    except Exception as e:
        logger.error("Decryption failed: %s", e)
        return ""

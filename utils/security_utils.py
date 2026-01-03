# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import base64
import hashlib
import hmac
from utils.path_utils import get_app_data_path

SECRET_FILE = "secret.key"


def _get_or_create_master_key():
    key_path = os.path.join(get_app_data_path(), SECRET_FILE)

    if os.path.exists(key_path):
        try:
            with open(key_path, 'rb') as f:
                key = f.read()
                if len(key) == 32:
                    return key
        except Exception:
            pass

    # Create new key
    key = os.urandom(32)
    try:
        # Set restrictive permissions on creation (Unix only, Windows ignores this mostly)
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(key)
    except Exception:
        # Fallback: if we can't write file, use a volatile memory key (lost on restart)
        return key

    return key


def encrypt_text(text: str) -> str:
    if not text: return ""
    try:
        master_key = _get_or_create_master_key()
        salt = os.urandom(16)

        # Derive a session key using PBKDF2
        session_key = hashlib.pbkdf2_hmac('sha256', master_key, salt, 10000)

        text_bytes = text.encode('utf-8')
        encrypted_bytes = bytearray()

        # XOR Encryption
        key_len = len(session_key)
        for i, b in enumerate(text_bytes):
            encrypted_bytes.append(b ^ session_key[i % key_len])

        # Calculate HMAC for integrity
        signature = hmac.new(master_key, salt + encrypted_bytes, hashlib.sha256).digest()

        # Format: Salt(16b) + Signature(32b) + Data
        payload = salt + signature + encrypted_bytes

        return "ENC:" + base64.b64encode(payload).decode('utf-8')
    except Exception:
        return text  # Fallback


def decrypt_text(text: str) -> str:
    if not text or not text.startswith("ENC:"):
        return text

    try:
        master_key = _get_or_create_master_key()
        payload = base64.b64decode(text[4:])

        if len(payload) < 48:  # 16 (salt) + 32 (hmac)
            return ""

        salt = payload[:16]
        signature = payload[16:48]
        encrypted_bytes = payload[48:]

        # Verify HMAC
        expected_signature = hmac.new(master_key, salt + encrypted_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            return ""  # Tampered data or wrong key

        # Decrypt
        session_key = hashlib.pbkdf2_hmac('sha256', master_key, salt, 10000)
        decrypted_bytes = bytearray()
        key_len = len(session_key)

        for i, b in enumerate(encrypted_bytes):
            decrypted_bytes.append(b ^ session_key[i % key_len])

        return decrypted_bytes.decode('utf-8')
    except Exception:
        return ""
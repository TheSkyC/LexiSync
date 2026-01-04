# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import base64
import hashlib
import hmac
from utils.path_utils import get_app_data_path
from utils.localization import _


SECRET_FILE = "secret.key"


def _get_or_create_master_key() -> bytes:
    key_path = os.path.join(get_app_data_path(), SECRET_FILE)

    if os.path.exists(key_path):
        try:
            with open(key_path, 'rb') as f:
                key = f.read()
                if len(key) == 32:
                    return key
        except Exception as e:
            pass

    # Create new key
    key = os.urandom(32)
    try:
        with open(key_path, 'wb') as f:
            f.write(key)

        if sys.platform != 'win32':
            os.chmod(key_path, 0o600)

    except Exception as e:
        print(f"DEBUG: Exception caught in _get_or_create_master_key: {e}")  # Your debug print
        error_message = _(
            "Could not create or write the encryption key file at:\n{path}\n\n"
            "Please check folder permissions, disk space, and antivirus settings.\n\n"
            "Technical Details: {error}"
        ).format(path=key_path, error=str(e))
        raise IOError(error_message) from e

    return key


def encrypt_text(text: str) -> str:
    if not text: return ""

    master_key = _get_or_create_master_key()

    try:
        text_bytes = text.encode('utf-8')
        salt = os.urandom(16)

        keystream = hashlib.shake_256(master_key + salt).digest(len(text_bytes))
        encrypted_bytes = bytes(a ^ b for a, b in zip(text_bytes, keystream))
        signature = hmac.new(master_key, salt + encrypted_bytes, hashlib.sha256).digest()

        payload = salt + signature + encrypted_bytes

        return "ENC:" + base64.b64encode(payload).decode('utf-8')
    except Exception:
        return ""


def decrypt_text(text: str) -> str:
    if not text or not text.startswith("ENC:"):
        return text

    master_key = _get_or_create_master_key()

    try:
        try:
            payload = base64.b64decode(text[4:])
        except Exception:
            return ""

        if len(payload) < 48:
            return ""

        salt = payload[:16]
        signature = payload[16:48]
        encrypted_bytes = payload[48:]

        expected_signature = hmac.new(master_key, salt + encrypted_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            return ""

        keystream = hashlib.shake_256(master_key + salt).digest(len(encrypted_bytes))
        decrypted_bytes = bytes(a ^ b for a, b in zip(encrypted_bytes, keystream))

        return decrypted_bytes.decode('utf-8')
    except Exception:
        return ""
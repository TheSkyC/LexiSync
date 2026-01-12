# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import base64
import hashlib
import hmac
import logging
import keyring
import keyring.errors
from utils.path_utils import get_app_data_path
from utils.localization import _

logger = logging.getLogger(__name__)

SECRET_FILE = "secret.key"
KEYRING_SERVICE = "LexiSync"
KEYRING_USER = "master_key"


def _get_or_create_master_key() -> bytes:
    """
    获取主密钥。
    策略：
    1. 尝试从系统 Keyring 获取。
    2. 如果 Keyring 不可用或为空，尝试从本地 secret.key 文件获取（回退机制）。
    3. 如果都不存在，生成新密钥。
    4. 保存时，优先存入 Keyring；如果失败，则存入本地文件。
    """

    # 1. 尝试从 Keyring 读取
    try:
        key_hex = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        if key_hex:
            # Keyring 存储的是 Hex 字符串，转回 bytes
            return bytes.fromhex(key_hex)
    except Exception as e:
        logger.warning(f"Keyring lookup failed (will try local file): {e}")

    # 2. Keyring 没找到或报错，尝试读取本地文件 (Fallback)
    key_path = os.path.join(get_app_data_path(), SECRET_FILE)
    key = None

    if os.path.exists(key_path):
        try:
            with open(key_path, 'rb') as f:
                read_data = f.read()
                if len(read_data) == 32:
                    key = read_data
                    logger.info("Loaded master key from local file (fallback).")
        except Exception as e:
            logger.error(f"Failed to read local key file: {e}")

    # 3. 如果都没有，生成新密钥
    if not key:
        logger.info("Generating new master key.")
        key = os.urandom(32)

    # 4. 保存密钥 (尝试 Keyring -> 失败则保存文件)
    saved_to_keyring = False
    try:
        # Keyring 需要存储字符串，所以将 bytes 转为 hex
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key.hex())
        saved_to_keyring = True
        logger.info("Master key saved to system Keyring.")
    except Exception as e:
        logger.error(f"Failed to save key to Keyring: {e}")

    # 如果 Keyring 保存失败，则保存到文件
    if not saved_to_keyring:
        try:
            with open(key_path, 'wb') as f:
                f.write(key)

            # 设置文件权限 (仅限 Unix/Linux)
            if sys.platform != 'win32':
                os.chmod(key_path, 0o600)

            logger.warning(f"Master key saved to local file as fallback: {key_path}")
        except Exception as e:
            error_message = _(
                "Critical Security Error: Could not save master key to Keyring OR local file.\n"
                "Path: {path}\n"
                "Error: {error}"
            ).format(path=key_path, error=str(e))
            raise IOError(error_message) from e

    return key


def encrypt_text(text: str) -> str:
    if not text: return ""

    try:
        master_key = _get_or_create_master_key()

        text_bytes = text.encode('utf-8')
        salt = os.urandom(16)

        # 扩展密钥
        keystream = hashlib.shake_256(master_key + salt).digest(len(text_bytes))
        encrypted_bytes = bytes(a ^ b for a, b in zip(text_bytes, keystream))
        signature = hmac.new(master_key, salt + encrypted_bytes, hashlib.sha256).digest()

        payload = salt + signature + encrypted_bytes

        return "ENC:" + base64.b64encode(payload).decode('utf-8')
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return ""


def decrypt_text(text: str) -> str:
    if not text or not text.startswith("ENC:"):
        return text

    try:
        master_key = _get_or_create_master_key()

        try:
            payload = base64.b64decode(text[4:])
        except Exception:
            return ""

        if len(payload) < 48:  # 16 (salt) + 32 (signature)
            return ""

        salt = payload[:16]
        signature = payload[16:48]
        encrypted_bytes = payload[48:]

        expected_signature = hmac.new(master_key, salt + encrypted_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("Decryption signature mismatch.")
            return ""

        keystream = hashlib.shake_256(master_key + salt).digest(len(encrypted_bytes))
        decrypted_bytes = bytes(a ^ b for a, b in zip(encrypted_bytes, keystream))

        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return ""
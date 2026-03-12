# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import platform
import re
import stat
import subprocess
import tarfile
import threading

import requests

from lexisync.utils.path_utils import get_app_data_path

from .base import BaseTunnelProvider, TunnelStatus

logger = logging.getLogger(__name__)


class CloudflareProvider(BaseTunnelProvider):
    def __init__(self):
        super().__init__()
        self.process = None
        self._stop_event = threading.Event()

        # 确定二进制文件存放目录
        self.bin_dir = os.path.join(get_app_data_path(), "bin")
        os.makedirs(self.bin_dir, exist_ok=True)

        system = platform.system().lower()
        ext = ".exe" if system == "windows" else ""
        self.binary_path = os.path.join(self.bin_dir, f"cloudflared{ext}")

    def is_installed(self) -> bool:
        return os.path.exists(self.binary_path)

    def _get_remote_filename(self):
        sys_name = platform.system().lower()
        machine = platform.machine().lower()
        is_64 = "64" in machine or "x86_64" in machine

        if sys_name == "windows":
            return "cloudflared-windows-amd64.exe" if is_64 else "cloudflared-windows-386.exe"
        if sys_name == "darwin":
            # macOS 始终是 .tgz 格式
            return "cloudflared-darwin-arm64.tgz" if "arm" in machine else "cloudflared-darwin-amd64.tgz"
        if sys_name == "linux":
            if "arm" in machine:
                return "cloudflared-linux-arm64" if is_64 else "cloudflared-linux-arm"
            return "cloudflared-linux-amd64" if is_64 else "cloudflared-linux-386"
        return ""

    def download_binary(self, progress_callback) -> bool:
        remote_file = self._get_remote_filename()
        if not remote_file:
            self.error_message = f"Unsupported platform: {platform.system()} {platform.machine()}"
            return False

        url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{remote_file}"

        temp_path = self.binary_path + ".download"

        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and progress_callback:
                            progress_callback(int((downloaded / total_size) * 100))

            # --- 后处理逻辑 ---
            if remote_file.endswith(".tgz"):
                # 处理 macOS 的压缩包
                with tarfile.open(temp_path, "r:gz") as tar:
                    # 寻找压缩包内的二进制文件
                    tar.extractall(path=self.bin_dir)
                    extracted_path = os.path.join(self.bin_dir, "cloudflared")
                    if os.path.exists(extracted_path):
                        if os.path.exists(self.binary_path):
                            os.remove(self.binary_path)
                        os.rename(extracted_path, self.binary_path)
                os.remove(temp_path)
            else:
                # Windows/Linux 直接重命名
                if os.path.exists(self.binary_path):
                    os.remove(self.binary_path)
                os.rename(temp_path, self.binary_path)

            # 赋予执行权限 (Unix)
            if platform.system().lower() != "windows":
                st = os.stat(self.binary_path)
                os.chmod(self.binary_path, st.st_mode | stat.S_IEXEC)

            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            self.error_message = str(e)
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

    def start(self, local_port: int, config: dict, status_callback, log_callback):
        self.status = TunnelStatus.CONNECTING
        self._stop_event.clear()
        status_callback(self.status, "")

        mode = config.get("mode", "quick")
        token = config.get("token", "").strip()

        cmd = [self.binary_path]
        if mode == "named" and token:
            cmd.extend(["tunnel", "--no-autoupdate", "run", "--token", token])
        else:
            cmd.extend(["tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{local_port}"])

        try:
            # Cloudflared 输出到 stderr
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "windows" else 0,
            )

            # 启动读取线程
            threading.Thread(target=self._read_output, args=(status_callback, log_callback, mode), daemon=True).start()

        except Exception as e:
            self.status = TunnelStatus.ERROR
            self.error_message = str(e)
            status_callback(self.status, self.error_message)

    def _read_output(self, status_callback, log_callback, mode):
        url_pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

        for line in iter(self.process.stdout.readline, ""):
            if self._stop_event.is_set():
                break

            line = line.strip()
            if not line:
                continue

            logger.debug(f"[cloudflared] {line}")
            log_callback(line)

            if self.status == TunnelStatus.CONNECTING:
                if mode == "quick":
                    match = url_pattern.search(line)
                    if match:
                        found_url = match.group(0)
                        logger.info(f"Detected Cloudflare Quick Tunnel URL: {found_url}")
                        self.public_url = found_url
                        self.status = TunnelStatus.ONLINE
                        status_callback(self.status, self.public_url)
                elif mode == "named":
                    if "Registered tunnel connection" in line or "Connection established" in line:
                        logger.info("Cloudflare Named Tunnel established.")
                        self.public_url = "Custom Domain"
                        self.status = TunnelStatus.ONLINE
                        status_callback(self.status, self.public_url)

    def stop(self):
        self._stop_event.set()
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()
            self.process = None
        self.status = TunnelStatus.DISCONNECTED
        self.public_url = ""

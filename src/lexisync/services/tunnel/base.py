# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from enum import Enum


class TunnelStatus(Enum):
    DISCONNECTED = "disconnected"
    DOWNLOADING = "downloading"
    CONNECTING = "connecting"
    ONLINE = "online"
    ERROR = "error"


class BaseTunnelProvider(ABC):
    def __init__(self):
        self.status = TunnelStatus.DISCONNECTED
        self.public_url = ""
        self.error_message = ""

    @abstractmethod
    def start(self, local_port: int, config: dict, status_callback, log_callback):
        """启动穿透服务"""
        pass

    @abstractmethod
    def stop(self):
        """停止穿透服务"""
        pass

    @abstractmethod
    def is_installed(self) -> bool:
        """检查依赖的二进制文件是否已安装"""
        pass

    @abstractmethod
    def download_binary(self, progress_callback) -> bool:
        """下载所需的二进制文件"""
        pass

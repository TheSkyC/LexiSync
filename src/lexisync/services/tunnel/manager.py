# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QObject, QThread, Signal

from .base import TunnelStatus
from .cloudflare import CloudflareProvider


class DownloadWorker(QThread):
    progress = Signal(int)
    finished = Signal(bool)

    def __init__(self, provider):
        super().__init__()
        self.provider = provider

    def run(self):
        success = self.provider.download_binary(self.progress.emit)
        self.finished.emit(success)


class TunnelManager(QObject):
    status_changed = Signal(object, str)  # status_enum, url_or_error
    log_received = Signal(str)
    download_progress = Signal(int)

    def __init__(self):
        super().__init__()
        self.providers = {"cloudflare": CloudflareProvider()}
        self.active_provider = None
        self._download_worker = None

    def start_tunnel(self, provider_name: str, local_port: int, config: dict):
        self.stop_tunnel()

        provider = self.providers.get(provider_name)
        if not provider:
            self.status_changed.emit(TunnelStatus.ERROR, f"Unknown provider: {provider_name}")
            return

        self.active_provider = provider

        if not provider.is_installed():
            self.status_changed.emit(TunnelStatus.DOWNLOADING, "")
            self._download_worker = DownloadWorker(provider)
            self._download_worker.progress.connect(self.download_progress.emit)
            self._download_worker.finished.connect(
                lambda success: self._on_download_finished(success, local_port, config)
            )
            self._download_worker.start()
        else:
            provider.start(local_port, config, self._on_status_update, self.log_received.emit)

    def _on_download_finished(self, success, local_port, config):
        if success:
            self.active_provider.start(local_port, config, self._on_status_update, self.log_received.emit)
        else:
            self.status_changed.emit(TunnelStatus.ERROR, self.active_provider.error_message)

    def _on_status_update(self, status, info):
        self.status_changed.emit(status, info)

    def stop_tunnel(self):
        if self.active_provider:
            self.active_provider.stop()
            self.active_provider = None
            self.status_changed.emit(TunnelStatus.DISCONNECTED, "")

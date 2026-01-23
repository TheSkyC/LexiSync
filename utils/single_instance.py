# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress
from PySide6.QtCore import QObject, Signal
import logging

logger = logging.getLogger(__name__)

SINGLE_INSTANCE_PORT = 20454
ACTIVATE_MSG = b"ACTIVATE_LEXISYNC"

class SingleInstanceServer(QObject):
    request_activation = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = QTcpServer(self)
        self.server.newConnection.connect(self._handle_new_connection)

    def start(self):
        if not self.server.listen(QHostAddress.LocalHost, SINGLE_INSTANCE_PORT):
            logger.error(f"SingleInstanceServer failed to listen on port {SINGLE_INSTANCE_PORT}")
            return False
        return True

    def _handle_new_connection(self):
        socket = self.server.nextPendingConnection()
        socket.readyRead.connect(lambda: self._read_data(socket))

    def _read_data(self, socket):
        data = socket.readAll().data()
        if data == ACTIVATE_MSG:
            self.request_activation.emit()
        socket.disconnectFromHost()


def raise_existing_instance():
    """新实例调用：尝试连接旧实例，成功则发送唤醒信号并返回 True"""
    socket = QTcpSocket()
    socket.connectToHost(QHostAddress.LocalHost, SINGLE_INSTANCE_PORT)

    if socket.waitForConnected(500):
        socket.write(ACTIVATE_MSG)
        socket.waitForBytesWritten(500)
        socket.disconnectFromHost()
        return True
    return False
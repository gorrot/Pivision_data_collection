import os
from PyQt5.QtWidgets import QSystemTrayIcon, QStyle
from PyQt5.QtGui import QIcon


def _icon_path():
    """托盘图标路径：优先 images/icon.png，否则本目录 icon.png"""
    base = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(base, "images", "icon.png"), os.path.join(base, "icon.png")):
        if os.path.isfile(path):
            return path
    return ""


class NotificationManager:
    """System tray notification manager."""

    _shared_tray_icon = None
    _owns_tray_icon = False

    @classmethod
    def set_tray_icon(cls, tray_icon):
        """Use external tray icon to avoid creating duplicate tray entries."""
        cls._shared_tray_icon = tray_icon
        cls._owns_tray_icon = False

    def __init__(self):
        if NotificationManager._shared_tray_icon is None:
            tray_icon = QSystemTrayIcon()
            icon_path = _icon_path()
            if icon_path:
                tray_icon.setIcon(QIcon(icon_path))
            else:
                # 无图标时使用系统默认图标，避免 QSystemTrayIcon::setVisible: No Icon set
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app and app.style():
                    tray_icon.setIcon(app.style().standardIcon(QStyle.SP_ComputerIcon))
            tray_icon.setVisible(True)
            NotificationManager._shared_tray_icon = tray_icon
            NotificationManager._owns_tray_icon = True
        self.tray_icon = NotificationManager._shared_tray_icon

    def show_notification(self, title, message):
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 5000)

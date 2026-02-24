import sys
import threading
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel,
    QListWidget, QMessageBox, QComboBox, QHBoxLayout, QSpinBox, QSystemTrayIcon, QMenu, QAction, QCheckBox
)
from PyQt5.QtGui import QIcon, QFont
from PIVdata2 import (
    b2_mill_changed, 
    mill_changed, 
    concurrent_execute, 
    empyty_mill_confirm,
    belt_status_monitor
)

import PIVdata2
from warn_gui import NotificationManager


def _icon_path():
    """图标路径：优先 images/icon.png，否则本目录 icon.png"""
    base = os.path.dirname(os.path.abspath(__file__))
    for name in (os.path.join(base, "images", "icon.png"), os.path.join(base, "icon.png")):
        if os.path.isfile(name):
            return name
    return ""


class TaskConfigGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.task_configs = []  # 任务列表
        self.detection_interval = 30  # 默认检测间隔 10 秒
        self.default_user = "U0662"
        self.default_password = "LGu0662"
        self.feishu_enable = None
        self.flask_server_url = "http://101.34.158.244:5000"  # Flask服务器地址
        # self.flask_server_url = "http://192.168.0.131:5000"#本地测试

        self.task_thread = None
        self.stop_event = threading.Event()
        self._is_exiting = False
        self.initUI()

    def initUI(self):
        self.setWindowTitle("🔧 PIVision 任务管理")
        self.setGeometry(200, 200, 600, 500)
        icon_path = _icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout()
        font = QFont("Arial", 14)

        self.url_label = QLabel("🔗 目标网址:")
        self.url_label.setFont(font)
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("请输入目标网址...")
        self.url_entry.setFont(font)
        layout.addWidget(self.url_label)
        layout.addWidget(self.url_entry)

        self.user_label = QLabel("👤 用户名:")
        self.user_label.setFont(font)
        self.user_entry = QLineEdit(self.default_user)
        self.user_entry.setFont(font)
        layout.addWidget(self.user_label)
        layout.addWidget(self.user_entry)

        self.pass_label = QLabel("🔑 密码:")
        self.pass_label.setFont(font)
        self.pass_entry = QLineEdit(self.default_password)
        self.pass_entry.setEchoMode(QLineEdit.Password)
        self.pass_entry.setFont(font)
        layout.addWidget(self.pass_label)
        layout.addWidget(self.pass_entry)

        self.task_label = QLabel("⚙️ 任务类型:")
        self.task_label.setFont(font)
        self.task_combo = QComboBox()
        self.task_combo.addItems(["2炉倒磨检测", "1,3,4炉倒磨检测（含5-8机组数据）", "空仓统计", "皮带状态检测"])
        self.task_combo.setFont(font)
        layout.addWidget(self.task_label)
        layout.addWidget(self.task_combo)

        self.interval_label = QLabel("⏳ 检测间隔（秒）:")
        self.interval_label.setFont(font)
        self.interval_input = QSpinBox()
        self.interval_input.setFont(font)
        self.interval_input.setRange(1, 3600)
        self.interval_input.setValue(self.detection_interval)
        layout.addWidget(self.interval_label)
        layout.addWidget(self.interval_input)

        self.flask_label = QLabel("🌐 Flask服务器地址:")
        self.flask_label.setFont(font)
        self.flask_entry = QLineEdit(self.flask_server_url)
        self.flask_entry.setPlaceholderText("例如: http://192.168.1.100:5000")
        self.flask_entry.setFont(font)
        layout.addWidget(self.flask_label)
        layout.addWidget(self.flask_entry)

        self.task_list = QListWidget()
        self.task_list.setFont(font)
        layout.addWidget(self.task_list)

        button_layout = QHBoxLayout()
        self.add_task_button = QPushButton("➕ 添加任务")
        self.add_task_button.setFont(font)
        self.add_task_button.clicked.connect(self.add_task)
        button_layout.addWidget(self.add_task_button)

        self.remove_task_button = QPushButton("🗑 删除任务")
        self.remove_task_button.setFont(font)
        self.remove_task_button.clicked.connect(self.remove_task)
        button_layout.addWidget(self.remove_task_button)

        layout.addLayout(button_layout)

        self.confirm_button = QPushButton("✅ 确认并运行")
        self.confirm_button.setFont(font)
        self.confirm_button.clicked.connect(self.confirm_tasks)
        layout.addWidget(self.confirm_button)

        self.exit_button = QPushButton("❌ 退出")
        self.exit_button.setFont(font)
        self.exit_button.clicked.connect(self.exit_app)
        layout.addWidget(self.exit_button)

        self.feishu_checkbox = QCheckBox("推送至飞书", self)
        self.feishu_checkbox.setFont(font)
        self.feishu_checkbox.setChecked(True)
        layout.addWidget(self.feishu_checkbox)

        self.setLayout(layout)

        self.tray_icon = QSystemTrayIcon(self)
        if icon_path:
            self.tray_icon.setIcon(QIcon(icon_path))
        self.tray_icon.setToolTip("PIVision 任务管理（左键/双击显示窗口，右键菜单退出）")
        tray_menu = QMenu(self)
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self._show_and_focus)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        quit_action = QAction("退出程序", self)
        quit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
        NotificationManager.set_tray_icon(self.tray_icon)

    def _show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self._show_and_focus()

    def closeEvent(self, event):
        if self._is_exiting:
            event.accept()
            return
        event.ignore()
        self.hide()
        if getattr(self, 'tray_icon', None) is not None:
            self.tray_icon.showMessage(
                "PIVision 监控系统",
                "程序仍在后台运行。点击托盘图标可恢复窗口。",
                QSystemTrayIcon.Information,
                3000
            )

    def add_task(self):
        TASK_MAPPING = {
            "2炉倒磨检测": b2_mill_changed,
            "1,3,4炉倒磨检测（含5-8机组数据）": mill_changed,
            "空仓统计": empyty_mill_confirm,
            "皮带状态检测": belt_status_monitor
        }
        url = self.url_entry.text().strip()
        user = self.user_entry.text().strip()
        password = self.pass_entry.text().strip()
        task_type = self.task_combo.currentText()

        if not url or not user or not password:
            QMessageBox.warning(self, "⚠️ 输入错误", "请填写所有字段！")
            return

        if task_type not in TASK_MAPPING:
            QMessageBox.warning(self, "⚠️ 任务类型错误", f"未知任务类型: {task_type}")
            return

        task_func = TASK_MAPPING[task_type]
        feishu_enabled = self.feishu_checkbox.isChecked()
        task_config = (url, user, password, task_func, feishu_enabled)
        self.task_configs.append(task_config)
        self.task_list.addItem(f"🔹 {task_type.upper()} | {url} | {user}")

        self.url_entry.clear()
        self.user_entry.clear()
        self.pass_entry.clear()

    def remove_task(self):
        selected_item = self.task_list.currentRow()
        if selected_item != -1:
            self.task_configs.pop(selected_item)
            self.task_list.takeItem(selected_item)

    def confirm_tasks(self):
        if not self.task_configs:
            QMessageBox.warning(self, "⚠️ 错误", "没有任务可执行！")
            return

        if self.task_thread and self.task_thread.is_alive():
            QMessageBox.information(self, "提示", "数据采集已在运行中，请先退出当前任务。")
            self.hide()
            return

        self.detection_interval = self.interval_input.value()
        
        flask_url = self.flask_entry.text().strip()
        if flask_url:
            PIVdata2.FLASK_RECEIVER_URL = flask_url
            print(f"✅ Flask服务器地址已设置为: {flask_url}")
        else:
            PIVdata2.FLASK_RECEIVER_URL = self.flask_server_url
            print(f"✅ Flask服务器地址使用默认值: {self.flask_server_url}")

        QMessageBox.information(self, "✅ 任务已启动", f"检测间隔: {self.detection_interval} 秒\nFlask地址: {PIVdata2.FLASK_RECEIVER_URL}")
        self.hide()

        self.stop_event.clear()
        self.task_thread = threading.Thread(
            target=self._run_tasks,
            name="piv-collector",
            daemon=True
        )
        self.task_thread.start()

    def _run_tasks(self):
        try:
            PIVdata2.concurrent_execute(self.task_configs, self.detection_interval, self.stop_event)
        except Exception as e:
            print(f"❌ 任务线程异常退出: {e}")

    def exit_app(self):
        self._is_exiting = True
        self.stop_event.set()

        if self.task_thread and self.task_thread.is_alive():
            self.task_thread.join(timeout=8)

        if getattr(self, "tray_icon", None) is not None:
            self.tray_icon.hide()

        app = QApplication.instance()
        if app is not None:
            app.quit()

        if self.task_thread and self.task_thread.is_alive():
            os._exit(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = TaskConfigGUI()
    gui.show()
    sys.exit(app.exec_())

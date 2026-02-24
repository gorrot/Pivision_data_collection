import time
import threading
import os
import sys
import pyautogui
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import numpy as np
from collections import defaultdict
from datetime import datetime, timedelta
import empty_confirm
from empty_confirm import Previous_records_manger
import stove_turned
from stove_turned import HTMLColorExtractor
from typing import Optional, Tuple
from plyer import notification
import robot_sendmsg as rs
from warn_gui import NotificationManager
import requests
import logging

# 设置日志级别，减少SSL错误信息的输出
logging.getLogger('selenium').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.ERROR)

DETECTION_INTERVAL = 10  # 检测间隔时间（秒）
FLASK_TIMEOUT_SECONDS = 10
FLASK_RETRY_COUNT = 2
FLASK_RETRY_BACKOFF_SECONDS = 1.5

# Flask接收服务配置：与 config.json 中 flask.base_url 统一，保证一期/三期数据发往同一服务器
def _get_flask_receiver_url():
    try:
        root = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(root, "config.json")
        if os.path.isfile(config_path):
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            base_url = (data.get("flask") or {}).get("base_url")
            if base_url and isinstance(base_url, str):
                return base_url.rstrip("/")
    except Exception:
        pass
    return "http://192.168.0.102:5000"  # 默认与 App 测试服务器一致

FLASK_RECEIVER_URL = _get_flask_receiver_url()
FLASK_ENABLED = True  # 是否启用Flask推送
# 启动时打印，便于确认与 App 连接同一服务器
if __name__ != "__main__":
    pass  # 被 import 时不打印
else:
    print(f"📡 数据发送地址（config.json flask.base_url）: {FLASK_RECEIVER_URL}，请确保 App 连接同一服务器")

# ... existing code ...

class ElementConfig:
    """页面元素配置类"""
    def __init__(self):
        self.empty_mills = self._init_empty_mills()
        self.changed_mills = self._init_changed_mills()
        self.load_values = self._init_load_values()
        self.b2_mills = self._init_b2_mills()
        self.belt_lines = self._init_belt_lines()  # 皮带line元素配置
        self.phase3_load_ids = self._init_phase3_load_ids()  # 三期 #5-#8 负荷
        self.phase3_mill_ids = self._init_phase3_mill_ids()  # 三期 #5-#8 磨煤机 A-F

    def _init_phase3_load_ids(self):
        """三期 #5-#8 机组负荷：g_id 与 tspan_id"""
        return [
            ("Value5", "Value5_pbTextEl_Value"),
            ("Value6", "Value6_pbTextEl_Value"),
            ("Value7", "Value7_pbTextEl_Value"),
            ("Value8", "Value8_pbTextEl_Value"),
        ]

    def _init_phase3_mill_ids(self):
        """三期 #5-#8 磨煤机状态：每机组 A~F 顺序的 text 元素 id"""
        return {
            "#5机组": ["Text47_pbTextEl", "Text48_pbTextEl", "Text31_pbTextEl", "Text32_pbTextEl", "Text33_pbTextEl", "Text34_pbTextEl"],
            "#6机组": ["Text40_pbTextEl", "Text39_pbTextEl", "Text38_pbTextEl", "Text35_pbTextEl", "Text37_pbTextEl", "Text36_pbTextEl"],
            "#7机组": ["Text46_pbTextEl", "Text45_pbTextEl", "Text44_pbTextEl", "Text41_pbTextEl", "Text43_pbTextEl", "Text42_pbTextEl"],
            "#8机组": ["Text56_pbTextEl", "Text55_pbTextEl", "Text52_pbTextEl", "Text49_pbTextEl", "Text51_pbTextEl", "Text50_pbTextEl"],
        }

    def _init_empty_mills(self):
        specified_values = [37, 101, 38, 102, 103, 104, 105, 106, 41, 107, 42, 108,
                          43, 109, 44, 110, 45, 111, 46, 112, 47, 113, 48, 114,
                          49, 115, 50, 116, 51, 117, 52, 118, 53, 119, 54, 120,
                          55, 121, 122, 123, 124, 125, 58, 126, 59, 127, 60, 128]
        return [(f"Value{num}", f"Value{num}_pbTextEl_Value") for num in specified_values]

    def _init_changed_mills(self):
        return {
            "1号机组": ["Text59_pbTextEl", "Text58_pbTextEl", "Text57_pbTextEl", "Text60_pbTextEl"],
            "2号机组": ["Text62_pbTextEl", "Text63_pbTextEl", "Text64_pbTextEl", "Text61_pbTextEl"],
            "3号机组": ["Text66_pbTextEl", "Text67_pbTextEl", "Text68_pbTextEl", "Text65_pbTextEl"],
            "4号机组": ["Text70_pbTextEl", "Text71_pbTextEl", "Text72_pbTextEl", "Text69_pbTextEl"]
        }

    def _init_load_values(self):
        return [f"Value{i}_pbTextEl_Value" for i in range(1, 5)]

    def _init_b2_mills(self):
        return ["symm585", "symm7", "symm16", "symm17"]
    
    def _init_belt_lines(self):
        """
        初始化皮带line元素配置（一期 4A-9B + 三期 307-312 合并）
        格式: {line_id: belt_name}
        三期对应关系来自 PI Vision - 燃 料 加 仓.htm
        """
        phase1 = {
            "Line12_Line": "#4A皮带",
            "Line13_Line": "4B皮带",
            "Line3_Line": "5A皮带",
            "Line4_Line": "5B皮带",
            "Line5_Line": "6A皮带",
            "Line6_Line": "6B皮带",
            "Line7_Line": "7A皮带",
            "Line8_Line": "7B皮带",
            "Line9_Line": "8A皮带",
            "Line77_Line": "8B皮带",
            "Line11_Line": "9A皮带",
            "Line10_Line": "9B皮带"
        }
        phase3 = {
            "Line22_Line": "#307B",
            "Line23_Line": "#307A",
            "Line24_Line": "#308B",
            "Line25_Line": "#308A",
            "Line14_Line": "#309A",
            "Line15_Line": "#309B",
            "Line16_Line": "#310A",
            "Line17_Line": "#310B",
            "Line18_Line": "#311A",
            "Line19_Line": "#311B",
            "Line20_Line": "#312A",
            "Line21_Line": "#312B",
        }
        out = dict(phase1)
        out.update(phase3)
        return out

class ElementFinder:
    """元素查找策略类"""
    def __init__(self, soup):
        self.soup = soup

    def find_tspan_value(self, g_id: str, tspan_id: str) -> Optional[str]:
        """查找tspan元素的值"""
        try:
            g_element = self.soup.find("g", {"id": g_id})
            if not g_element:
                return None

            tspan_element = g_element.find("tspan", {"id": tspan_id})
            if not tspan_element:
                return None

            return tspan_element.text.strip()
        except Exception:
            return None

    def find_polygon_color(self, polygon_id: str) -> str:
        """查找多边形元素的填充颜色"""
        try:
            polygon = self.soup.find("polygon", {"id": polygon_id})
            if polygon:
                fill_color = polygon.get("fill")
                if fill_color:
                    return fill_color

            g_element = self.soup.find("g", id=polygon_id.replace("_pbTextEl", ""))
            if g_element:
                text_element = g_element.find("text", {"id": polygon_id})
            else:
                text_element = self.soup.find("text", {"id": polygon_id})

            if text_element:
                fill_color = text_element.get("fill")
                if fill_color:
                    return fill_color

            print(f"警告: 未找到元素 {polygon_id} 的颜色值")
            return "未知"
        except Exception as e:
            print(f"获取颜色时发生错误: {str(e)}")
            return "未知"
    
    def find_text_fill(self, text_id: str) -> str:
        """查找 text 元素的 fill 颜色（用于三期磨煤机 A-F 状态）"""
        try:
            text_el = self.soup.find("text", {"id": text_id})
            if text_el:
                fill = text_el.get("fill")
                if fill:
                    return fill
            g_id = text_id.replace("_pbTextEl", "")
            g_el = self.soup.find("g", {"id": g_id})
            if g_el:
                text_el = g_el.find("text", {"id": text_id})
                if text_el and text_el.get("fill"):
                    return text_el.get("fill")
            return "未知"
        except Exception:
            return "未知"

    def find_line_color(self, line_id: str) -> str:
        """查找line元素的stroke颜色（支持静态HTML与运行时 data-bind 后的属性）"""
        try:
            line_element = self.soup.find("line", {"id": line_id})
            if not line_element:
                print(f"警告: 未找到line元素 {line_id}")
                return "未知"
            stroke_color = line_element.get("stroke")
            if stroke_color and str(stroke_color).strip():
                return str(stroke_color).strip()
            for attr, value in (line_element.attrs or {}).items():
                if attr and attr.lower() == "stroke" and value:
                    return str(value).strip()
            style = line_element.get("style") or ""
            if isinstance(style, str) and "stroke" in style.lower():
                for part in style.split(";"):
                    if ":" in part and "stroke" in part.split(":")[0].strip().lower():
                        stroke_color = part.split(":", 1)[1].strip()
                        if stroke_color:
                            return stroke_color
            print(f"警告: line元素 {line_id} 没有stroke颜色属性")
            return "未知"
        except Exception as e:
            print(f"获取line颜色时发生错误: {str(e)}")
            return "未知"

class BrowserManager:
    """浏览器管理基类"""
    _lock = threading.Lock()  # 类级别锁用于同步键盘操作

    def __init__(self, url, domain_user, password):
        self.url = url
        self.domain_user = domain_user
        self.password = password
        self.driver = None
        self.soup = None

    def start(self):
        """启动浏览器并执行完整流程"""
        self._init_browser()
        self._handle_authentication()
        self._post_authentication()
        return self

    def _init_browser(self):
        os.environ['WDM_LOG_LEVEL'] = '0'
        os.environ['WDM_PRINT_FIRST_LINE'] = 'False'
        
        options = webdriver.ChromeOptions()
        options.add_argument("--window-title=PIVisionAutomator")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--ignore-certificate-errors-spki-list")
        options.add_argument("--ignore-ssl-errors-spki-list")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--log-level=3")
        options.add_argument("--silent")
        options.add_argument("--disable-logging")
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option('prefs', {
            'logging': {'level': 'OFF'},
            'profile.default_content_setting_values.notifications': 2
        })
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS  # EXE解压后的临时目录
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))  # 开发环境目录

        driver_path = os.path.join(base_dir, "chromedriver.exe")
        service = Service(executable_path=driver_path)
        self.driver = webdriver.Chrome(service=service, options=options)

        self.driver.get(self.url)

    def _handle_authentication(self):
        """处理登录认证弹窗"""
        time.sleep(2)
        with self._lock:
            self._focus_browser_window()
            self._perform_keyboard_actions()

    def _focus_browser_window(self):
        try:
            self.driver.switch_to.window(self.driver.current_window_handle)
            print("✅ 成功切换到 Selenium 窗口")
        except Exception as e:
            print(f"❌ 切换 Selenium 窗口失败: {e}")

    def _perform_keyboard_actions(self):
        pyautogui.write(self.domain_user)
        pyautogui.press('tab')
        pyautogui.write(self.password)
        pyautogui.press('enter')
        time.sleep(2)

    def _post_authentication(self):
        self.refresh()
        self.refresh()

    def get_page_source(self):
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        return self.driver.page_source

    def refresh(self):
        if self.driver:
            self.driver.refresh()
            time.sleep(8)

    def quit(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print(f"关闭浏览器时发生错误: {str(e)}")
            finally:
                self.driver = None


class PIVisionAutomator:
    """PIV自动化类"""
    def __init__(self, browser_manager: BrowserManager):
        self.browser = browser_manager
        self.config = ElementConfig()
        self.old_load = {}
        self.previous_mills_color = []
        self.finder = None
        self._op_lock = threading.RLock()

    def start(self):
        with self._op_lock:
            self.browser.start()
            self.update_finder()
            return self

    def update_finder(self):
        with self._op_lock:
            page_source = self.browser.get_page_source()
            soup = BeautifulSoup(page_source, "html.parser")
            self.finder = ElementFinder(soup)

    def refresh(self):
        with self._op_lock:
            self.browser.refresh()
            self.update_finder()

    def extract_empty_mills_values(self):
        with self._op_lock:
            if not self.finder:
                self.update_finder()

            total_values = []
            for g_id, tspan_id in self.config.empty_mills:
                value = self.finder.find_tspan_value(g_id, tspan_id)
                if value is not None:
                    total_values.append(value)

            if not total_values:
                print("警告：没有提取到任何数据！")
                return None

            try:
                return np.reshape(total_values, (4, 6, 2))
            except ValueError as e:
                print(f"重塑数组失败: {str(e)}")
                return None

    def extract_colors_value_b2(self):
        with self._op_lock:
            if not self.finder:
                self.update_finder()

            color_data_b2 = {}
            for idx, target_id in enumerate(self.config.b2_mills):
                color = self.finder.find_polygon_color(target_id)
                color_data_b2[f"{chr(65 + idx)} 磨"] = color
            return color_data_b2

    def Extract_Mill134_status(self):
        with self._op_lock:
            if not self.finder:
                self.update_finder()

            color_data = {}
            for unit, ids in self.config.changed_mills.items():
                if unit == "2号机组":
                    continue
                color_data[unit] = {}
                for idx, mill_id in enumerate(ids):
                    try:
                        color = self.finder.find_polygon_color(mill_id)
                        if color == "未知":
                            print(f"警告: {unit} 的 {chr(65 + idx)} 磨颜色获取失败")
                        color_data[unit][f"{chr(65 + idx)} 磨"] = color
                    except Exception as e:
                        print(f"获取 {unit} {chr(65 + idx)} 磨颜色时出错: {e}")
                        color_data[unit][f"{chr(65 + idx)} 磨"] = "未知"
            return color_data

    def extract_load_values(self):
        with self._op_lock:
            if not self.finder:
                self.update_finder()

            value_data = {}
            for idx, target_id in enumerate(self.config.load_values):
                value = self.finder.find_tspan_value("Value" + str(idx + 1), target_id)
                value_data[f"{idx + 1}机组当前负荷："] = value if value is not None else "未知"
            return value_data
    
    def extract_belt_status(self):
        with self._op_lock:
            if not self.finder:
                self.update_finder()

            if not self.config.belt_lines:
                return {}

            belt_status = {}
            for line_id, belt_name in self.config.belt_lines.items():
                color = self.finder.find_line_color(line_id)
                color_upper = color.upper() if color else ""

                if color_upper == "#FF0000" or color_upper == "RED":
                    status = "运行"
                elif color_upper == "#00FF00" or color_upper == "GREEN":
                    status = "停止"
                else:
                    status = "异常"
                status = "".join(ch for ch in status if not ch.isspace())
                belt_status[belt_name] = {
                    "color": color,
                    "status": status
                }

            return belt_status

    def extract_phase3_load(self):
        with self._op_lock:
            if not self.finder:
                self.update_finder()
            result = {}
            unit_labels = ["#5机组", "#6机组", "#7机组", "#8机组"]
            for i, (g_id, tspan_id) in enumerate(self.config.phase3_load_ids):
                val = self.finder.find_tspan_value(g_id, tspan_id)
                result[unit_labels[i]] = val if val is not None else "未知"
            return result

    def extract_phase3_mill_status(self):
        with self._op_lock:
            if not self.finder:
                self.update_finder()
            color_map = {"#FF0000": "运行", "#00FF00": "备用", "#FFFF00": "离线"}
            mill_names = ["A 磨", "B 磨", "C 磨", "D 磨", "E 磨", "F 磨"]
            result = {}
            for unit, text_ids in self.config.phase3_mill_ids.items():
                result[unit] = {}
                for idx, text_id in enumerate(text_ids):
                    color = self.finder.find_text_fill(text_id)
                    result[unit][mill_names[idx]] = color_map.get((color or "").upper(), "未知")
            return result

    def quit(self):
        with self._op_lock:
            if self.browser:
                self.browser.quit()


def empyty_mill_confirm(url, user, password, stop_event, compare_interval_minutes=3, feishu_enabled=False):
    global DETECTION_INTERVAL
    browser_manager = BrowserManager(url, user, password)
    automator = PIVisionAutomator(browser_manager)
    PRM = Previous_records_manger()
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    try:
        automator.start()
        last_compare_time = datetime.now()

        while not stop_event.is_set():
            automator.refresh()
            data = automator.extract_empty_mills_values()
            if data is not None:
                data_dict = empty_confirm.Array2Dict(data)
                mark1 = PRM.container_marked(data_dict)
                print(mark1)
                current_time = datetime.now()
                if current_time - last_compare_time >= timedelta(minutes=compare_interval_minutes):
                    result = PRM.double_marking(data_dict)
                    if result:
                        if feishu_enabled and result:
                            formatted_message = "; ".join([
                                f"{boiler} - {container}: {data['标记类型']} (当前值: {data['当前值']}, 历史值: {data['历史值']})"
                                for boiler, containers in result.items()
                                for container, data in containers.items()
                            ])
                            rs.send_message(f"🚨 空仓统计 {formatted_message}")

                        title = "🚨 空仓统计检测"
                        message = "; ".join([
                            f"{boiler} - {container}: {data['标记类型']} (当前值: {data['当前值']}, 历史值: {data['历史值']})"
                            for boiler, containers in result.items()
                            for container, data in containers.items()
                        ])
                        send_to_flask(title, message, "empty_mill", url=url, user=user)

                        save_result_to_file(result)
                    last_compare_time = current_time

            if stop_event.wait(DETECTION_INTERVAL):
                break
    except Exception as e:
        print(f"任务执行出错: {e}")
    finally:
        automator.quit()

def b2_mill_changed(url, user, password, stop_event, feishu_enabled=False):
    global DETECTION_INTERVAL
    color_map = {
        "#FFFF00": "离线",
        "#00FF00": "备用",
        "#FF0000": "运行",
        "未知": "未知状态"
    }

    def color_to_status(color):
        if not color or not isinstance(color, str):
            return "未知状态"
        key = color.strip().upper()
        return color_map.get(key, "未知状态")
    
    browser_manager = BrowserManager(url, user, password)
    automator = PIVisionAutomator(browser_manager)
    automator.start()
    
    automator.update_finder()
    init_color = automator.extract_colors_value_b2()
    print("⚙️ 初始基准颜色已记录")
    notification_manager = NotificationManager()

    try:
        print("✅ 磨煤机颜色监控已启动")
        while not stop_event.is_set():
            try:
                automator.refresh()
                current_time = datetime.now()
                new_data = automator.extract_colors_value_b2()
                if not new_data or all(value == "未知" for value in new_data.values()):
                    print("⚠️ 无有效颜色数据，跳过本次检测，保持旧状态")
                    if stop_event.wait(DETECTION_INTERVAL):
                        break
                    continue

                should_send_full_status = True

                if should_send_full_status:
                    print(f"📊 准备发送2号机组完整状态，数据: {new_data}")
                    mill_order = ["A 磨", "B 磨", "C 磨", "D 磨"]
                    full_status_lines = []
                    for mill_name in mill_order:
                        if mill_name in new_data:
                            mill_color = new_data[mill_name]
                            mill_status = color_to_status(mill_color)
                            full_status_lines.append(f"  ▸ {mill_name}: {mill_status} (当前状态)")
                    
                    if full_status_lines:
                        full_status_message = "\n".join(full_status_lines)
                        full_status_title = "📊 2号机组磨煤机完整状态"
                        print(f"📤 发送2号机组完整状态消息:\n{full_status_message}")
                        send_to_flask(full_status_title, full_status_message, "b2_mill_change", url=url, user=user)
                        print(f"✅ 已发送2号机组完整状态: {len(full_status_lines)} 个磨煤机")
                    else:
                        print("⚠️ 警告: 2号机组 full_status_lines 为空，无法发送完整状态")

                changed_mills = defaultdict(dict)

                for mill_name, new_color in new_data.items():
                    old_color = init_color.get(mill_name)

                    if old_color is None or new_color is None:
                        continue

                    if new_color and new_color != "未知" and old_color != new_color:
                        changed_mills["二号机组"][mill_name] = {
                            "old": color_to_status(old_color),
                            "new": color_to_status(new_color),
                            "time": current_time.strftime("%H:%M:%S")
                        }

                if changed_mills:
                    notification_title = "⚠️ 检测到2号机组倒磨操作!"
                    mills_data = changed_mills.get("二号机组", {})

                    notification_message = "\n".join([
                        f"  ▸ {mill}: {info['old']} → {info['new']} (检测时间: {info['time']})"
                        for mill, info in mills_data.items()
                    ])

                    if notification_message:
                        notification_manager.show_notification(notification_title, notification_message)
                        print("🔄 颜色变化检测成功，基准颜色已更新")

                        if feishu_enabled:
                            formatted_message = notification_message.replace("\n", " ").replace("\r", " ").strip()
                            rs.send_message(f"🚨 2号机组倒磨检测: {formatted_message}")

                        send_to_flask(notification_title, notification_message, "b2_mill_change", url=url, user=user)

                        init_color.update(new_data)

                print(f"当前颜色状态: {new_data}")
                print(f"检测到的变化: {changed_mills}")

            except Exception as e:
                print(f"⚠️ 检测过程中发生错误: {e}")

            if stop_event.wait(DETECTION_INTERVAL):
                break

    except KeyboardInterrupt:
        print("\n🛑 用户手动终止监控")
    except Exception as e:
        print(f"❌ 监控严重错误: {str(e)}")
    finally:
        automator.quit()
        print("✅ 浏览器已安全关闭")


def load_push(automator, notification_manager, stop_event, url=None, user=None):
    LOAD_CHECK_INTERVAL = 3600
    is_first_load = True
    
    while not stop_event.is_set():
        try:
            current_load = automator.extract_load_values()
            if not current_load:
                print("⚠️ 负荷数据获取失败，等待下次尝试")
                continue

            if is_first_load or not automator.old_load:
                for k in current_load.keys():
                    if k not in automator.old_load:
                        automator.old_load[k] = "100"
                is_first_load = False

            formatted_values = []
            for k, v in current_load.items():
                old_value = automator.old_load.get(k, None)
                arrow = ""
                if old_value is not None:
                    try:
                        old_float = float(old_value)
                        new_float = float(v)
                        if new_float < old_float:
                            arrow = " (下降)"
                        elif new_float == old_float:
                            arrow = " (持平)"
                        else:
                            arrow = " (上升)"
                    except (ValueError, TypeError):
                        arrow = " (新数据)"
                else:
                    arrow = " (初始值)"
                formatted_values.append(f"{k}: {v} MW{arrow}")

            load_message = "\n".join(formatted_values)

            notification_manager.show_notification("📊 负荷监控", load_message)
            print(f"📊 负荷数据已推送: {load_message}")

            title = "📊 负荷监控数据"
            send_to_flask(title, load_message, "load_monitor", url=url, user=user)

            automator.old_load = current_load.copy()

        except Exception as e:
            print(f"⚠️ 负荷监测出错: {str(e)}")

        if stop_event.wait(LOAD_CHECK_INTERVAL):
            print("🛑 负荷监测线程被终止")
            return


def mill_changed(url, user, password, stop_event, feishu_enabled=False):
    global DETECTION_INTERVAL
    color_map = {
        "#FFFF00": "离线",
        "#00FF00": "备用",
        "#FF0000": "运行",
        "未知": "未知状态"
    }

    browser_manager = BrowserManager(url, user, password)
    automator = PIVisionAutomator(browser_manager)
    automator.start()
    
    time.sleep(2)
    
    automator.update_finder()
    init_color = automator.Extract_Mill134_status()
    print("⚙️ 初始基准颜色已记录:", init_color)
    notification_manager = NotificationManager()
    
    load_thread = threading.Thread(target=load_push, args=(automator, notification_manager, stop_event, url, user))
    load_thread.start()

    FULL_STATUS_INTERVAL = 300
    last_full_status_time = datetime.now()
    first_full_status_sent = False
    old_phase3_mill = None

    try:
        print("✅ 磨煤机颜色监控已启动")
        while not stop_event.is_set():
            try:
                automator.refresh()
                current_time = datetime.now()

                try:
                    phase3_load = automator.extract_phase3_load()
                    if phase3_load:
                        print(f"📊 三期 #5-#8 机组负荷: {phase3_load}")
                        load_lines = [f"{k}: {v}" for k, v in phase3_load.items()]
                        send_to_flask("📊 三期负荷监控", "\n".join(load_lines), "phase3_load_monitor", url=url, user=user)
                        print(f"📤 已发送三期负荷到Flask (共 {len(phase3_load)} 个机组)")
                    else:
                        print("⚠️ 三期负荷数据未获取到，跳过推送")
                    phase3_mill = automator.extract_phase3_mill_status()
                    if phase3_mill:
                        print(f"📊 三期 #5-#8 机组磨煤机状态: {phase3_mill}")
                        mill_lines = []
                        for unit, mills in phase3_mill.items():
                            mill_lines.append(f"机组: {unit}")
                            for mname, status in mills.items():
                                mill_lines.append(f"  ▸ {mname}: {status} (当前状态)")
                        send_to_flask("📊 三期磨煤机状态", "\n".join(mill_lines), "phase3_mill_status", url=url, user=user)
                        print(f"📤 已发送三期磨煤机状态到Flask (共 {len(phase3_mill)} 个机组)")
                        changed_phase3_mills = {}
                        if old_phase3_mill is not None:
                            for unit, mills in phase3_mill.items():
                                old_mills = old_phase3_mill.get(unit, {})
                                for mname, new_status in mills.items():
                                    old_status = old_mills.get(mname)
                                    if old_status is not None and old_status != new_status and new_status != "未知":
                                        if unit not in changed_phase3_mills:
                                            changed_phase3_mills[unit] = {}
                                        changed_phase3_mills[unit][mname] = {
                                            "old": old_status,
                                            "new": new_status,
                                            "time": current_time.strftime("%H:%M:%S")
                                        }
                                        print(f"检测到三期变化 - {unit} {mname}: {old_status} -> {new_status}")
                            if changed_phase3_mills:
                                notification_message = "\n".join([
                                    f"机组: {unit}\n" + "\n".join([
                                        f"  ▸ {mill}: {info['old']} → {info['new']} (检测时间: {info['time']})"
                                        for mill, info in mills.items()
                                    ])
                                    for unit, mills in changed_phase3_mills.items()
                                ])
                                send_to_flask("⚠️ 检测到三期倒磨操作!", notification_message, "phase3_mill_change", url=url, user=user)
                                print(f"📤 已发送三期倒磨到Flask (共 {sum(len(m) for m in changed_phase3_mills.values())} 处变化)")
                        old_phase3_mill = {u: dict(m) for u, m in phase3_mill.items()}
                    else:
                        print("⚠️ 三期磨煤机状态未获取到，跳过推送")
                except Exception as e_phase3:
                    print(f"⚠️ 三期数据提取/推送跳过: {e_phase3}")

                new_data = automator.Extract_Mill134_status()
                if not new_data:
                    print("⚠️ 颜色数据获取失败，等待下次尝试")
                    if stop_event.wait(DETECTION_INTERVAL):
                        break
                    continue

                should_send_full_status = False
                if not first_full_status_sent:
                    should_send_full_status = True
                    first_full_status_sent = True
                    print("📊 首次启动，发送所有磨煤机完整状态")
                elif (current_time - last_full_status_time).total_seconds() >= FULL_STATUS_INTERVAL:
                    should_send_full_status = True
                    last_full_status_time = current_time
                    print("📊 定期发送所有磨煤机完整状态")
                
                should_send_full_status = True

                if should_send_full_status:
                    filtered_data = {unit: mills for unit, mills in new_data.items() if unit != "2号机组"}
                    
                    print(f"📊 准备发送完整状态，数据: {filtered_data}")
                    
                    if filtered_data:
                        full_status_message_parts = []
                        for unit, mills in filtered_data.items():
                            unit_status_lines = [f"机组: {unit}"]
                            mill_order = ["A 磨", "B 磨", "C 磨", "D 磨"]
                            for mill_name in mill_order:
                                if mill_name in mills:
                                    mill_color = mills[mill_name]
                                    mill_status = color_map.get(mill_color, mill_color)
                                    unit_status_lines.append(f"  ▸ {mill_name}: {mill_status} (当前状态)")
                            full_status_message_parts.append("\n".join(unit_status_lines))
                        
                        if full_status_message_parts:
                            full_status_message = "\n".join(full_status_message_parts)
                            full_status_title = "📊 磨煤机完整状态"
                            print(f"📤 发送完整状态消息:\n{full_status_message}")
                            send_to_flask(full_status_title, full_status_message, "mill134_change", url=url, user=user)
                            print(f"✅ 已发送完整状态: {len(filtered_data)} 个机组")
                    else:
                        print("⚠️ 警告: filtered_data 为空，无法发送完整状态")

                changed_mills = defaultdict(dict)

                for unit, mills in new_data.items():
                    unit_colors = init_color.get(unit, {})
                    for mill_name, new_color in mills.items():
                        if new_color == "未知":
                            continue
                            
                        old_color = unit_colors.get(mill_name)
                        if old_color is None:
                            continue

                        if new_color != "未知" and old_color != new_color:
                            changed_mills[unit][mill_name] = {
                                "old": color_map.get(old_color, old_color),
                                "new": color_map.get(new_color, new_color),
                                "time": current_time.strftime("%H:%M:%S")
                            }
                            print(f"检测到变化 - {unit} {mill_name}: {old_color} -> {new_color}")

                if changed_mills:
                    notification_title = "⚠️ 检测到倒磨操作!"

                    filtered_mills = {unit: mills for unit, mills in changed_mills.items() if unit != "2号机组"}

                    if not filtered_mills:
                        print("✅ 没有其他机组需要报警，跳过通知")
                    else:
                        notification_message = "\n".join([
                            f"机组: {unit}\n" + "\n".join([
                                f"  ▸ {mill}: {info['old']} → {info['new']} (检测时间: {info['time']})"
                                for mill, info in mills.items()
                            ])
                            for unit, mills in filtered_mills.items()
                        ])

                        if notification_message:
                            notification_manager.show_notification(notification_title, notification_message)
                            print("🔄 颜色变化检测成功，基准颜色已更新")
                            init_color.update(new_data)
                            formatted_message = notification_message.replace("\n", " ").replace("\r", " ").strip()
                            if feishu_enabled:
                                rs.send_message(f"🚨 倒磨检测 {formatted_message}")

                            send_to_flask(notification_title, notification_message, "mill134_change", url=url, user=user)

                print(f"当前颜色状态: {new_data}")
                print(f"检测到的变化: {changed_mills}")

            except Exception as inner_e:
                print(f"⚠️ 循环执行出错: {str(inner_e)}")
                if stop_event.wait(DETECTION_INTERVAL * 2):
                    break

            if stop_event.wait(DETECTION_INTERVAL):
                break

    except KeyboardInterrupt:
        print("\n🛑 用户手动终止监控")
    except Exception as e:
        print(f"❌ 监控严重错误: {str(e)}")
    finally:
        stop_event.set()
        load_thread.join()
        automator.quit()
        print("✅ 浏览器已安全关闭")

def concurrent_execute(configs, interval_time, stop_event):
    """并发执行多个自动化任务"""
    global DETECTION_INTERVAL
    DETECTION_INTERVAL = interval_time
    threads = []

    for config in configs:
        url, user, password, target_function, feishu_enable = config
        t = threading.Thread(target=target_function, args=(url, user, password, stop_event, feishu_enable), daemon=True)
        threads.append(t)
        t.start()

    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()

    for t in threads:
        t.join()

def belt_status_monitor(url, user, password, stop_event, feishu_enabled=False):
    global DETECTION_INTERVAL
    
    browser_manager = BrowserManager(url, user, password)
    automator = PIVisionAutomator(browser_manager)
    automator.start()
    
    time.sleep(2)
    
    automator.update_finder()
    init_belt_status = automator.extract_belt_status()
    print("⚙️ 初始皮带状态已记录:", init_belt_status)
    notification_manager = NotificationManager()
    
    try:
        print("✅ 皮带状态监控已启动")
        while not stop_event.is_set():
            try:
                automator.refresh()
                current_time = datetime.now()
                
                new_belt_status = automator.extract_belt_status()
                if not new_belt_status:
                    print("⚠️ 皮带状态数据获取失败或未配置，等待下次尝试")
                    if stop_event.wait(DETECTION_INTERVAL):
                        break
                    continue
                
                changed_belts = {}
                
                for belt_name, new_data in new_belt_status.items():
                    old_data = init_belt_status.get(belt_name)
                    
                    if old_data is None:
                        continue
                    
                    if new_data["status"] != old_data["status"]:
                        changed_belts[belt_name] = {
                            "old": old_data["status"],
                            "new": new_data["status"],
                            "old_color": old_data["color"],
                            "new_color": new_data["color"],
                            "time": current_time.strftime("%H:%M:%S")
                        }
                        print(f"检测到变化 - {belt_name}: {old_data['status']} -> {new_data['status']}")
                
                if changed_belts:
                    notification_title = "⚠️ 检测到皮带状态变化!"
                    
                    notification_message = "\n".join([
                        f"  ▸ {belt_name}: {info['old']} → {info['new']} (检测时间: {info['time']})"
                        for belt_name, info in changed_belts.items()
                    ])
                    
                    if notification_message:
                        notification_manager.show_notification(notification_title, notification_message)
                        print("🔄 皮带状态变化检测成功，基准状态已更新")
                        print(f"📝 变化消息内容:\n{notification_message}")
                        init_belt_status.update(new_belt_status)
                        formatted_message = notification_message.replace("\n", " ").replace("\r", " ").strip()
                        if feishu_enabled:
                            rs.send_message(f"🚨 皮带状态检测 {formatted_message}")
                        
                        print(f"📤 准备发送皮带状态变化到Flask...")
                        send_to_flask(notification_title, notification_message, "belt_status", url=url, user=user)
                
                current_status_message = "\n".join([
                    f"  ▸ {belt_name}: {data['status']} (当前状态)"
                    for belt_name, data in new_belt_status.items()
                ])
                
                if current_status_message:
                    current_status_title = "📊 皮带系统当前状态"
                    print(f"📤 准备发送皮带当前状态到Flask (共 {len(new_belt_status)} 条皮带)...")
                    send_to_flask(current_status_title, current_status_message, "belt_status", url=url, user=user)
                
                print(f"当前皮带状态: {new_belt_status}")
                print(f"检测到的变化: {changed_belts}")
                
            except Exception as inner_e:
                print(f"⚠️ 循环执行出错: {str(inner_e)}")
                if stop_event.wait(DETECTION_INTERVAL * 2):
                    break
            
            if stop_event.wait(DETECTION_INTERVAL):
                break
    
    except KeyboardInterrupt:
        print("\n🛑 用户手动终止监控")
    except Exception as e:
        print(f"❌ 监控严重错误: {str(e)}")
    finally:
        automator.quit()
        print("✅ 浏览器已安全关闭")

def get_logs_path():
    """确保 EXE 所在目录下的 `logs/` 目录存在，并返回正确路径"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    log_dir = os.path.join(base_path, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def send_to_flask(title, message, notification_type="mill_change", url=None, user=None):
    """发送检测数据到Flask接收服务"""
    if not FLASK_ENABLED:
        print(f"⚠️ Flask推送已禁用，跳过发送: {title[:30]}...")
        return

    data = {
        'title': title,
        'message': message,
        'type': notification_type,
        'timestamp': datetime.now().isoformat(),
        'url': url,
        'user': user
    }

    print(f"📤 准备发送到Flask: {notification_type}")
    print(f"   URL: {FLASK_RECEIVER_URL}/receive_detection")
    print(f"   标题: {title[:50]}...")
    print(f"   消息长度: {len(message)} 字符")

    endpoint = f"{FLASK_RECEIVER_URL}/receive_detection"
    max_attempts = FLASK_RETRY_COUNT + 1
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            print(f"🔁 Flask推送重试中 ({attempt}/{max_attempts})...")

        try:
            response = requests.post(
                endpoint,
                json=data,
                timeout=FLASK_TIMEOUT_SECONDS
            )

            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"✅ Flask推送成功: {result.get('message', '')} (ID: {result.get('data_id')})")
                except Exception as e:
                    print(f"⚠️ Flask推送响应解析失败: {e}，但状态码为200，数据可能已保存")
                return
            elif response.status_code == 500:
                print(f"⚠️ Flask推送返回500错误，但数据可能已保存（手机app可正常显示）")
                print(f"   响应内容: {response.text[:500]}")
                print(f"   提示: 请检查Flask服务器日志以查看具体错误")
                return
            else:
                print(f"❌ Flask推送失败: {response.status_code}")
                print(f"   响应内容: {response.text[:500]}")
                return

        except requests.exceptions.Timeout:
            print(f"❌ Flask推送超时: 请求超过{FLASK_TIMEOUT_SECONDS}秒未响应")
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Flask推送连接错误: 无法连接到服务器 {FLASK_RECEIVER_URL}")
            print(f"   错误详情: {e}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Flask推送异常: {e}")
        except Exception as e:
            import traceback
            print(f"❌ Flask推送错误: {e}")
            print(f"   错误堆栈:\n{traceback.format_exc()}")
            return

        if attempt < max_attempts:
            time.sleep(FLASK_RETRY_BACKOFF_SECONDS * attempt)

    print(f"❌ Flask推送最终失败: 共尝试 {max_attempts} 次")

def save_result_to_file(result):
    """
    将检测结果按日期存入日志文件，避免重复记录。
    """
    log_dir = get_logs_path()
    current_date = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"result_{current_date}.txt")

    current_log = (
        f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🔹 结果: {result}\n"
        f"{'-' * 60}\n"
    )
    result_signature = f"🔹 结果: {result}\n"

    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as file:
            if result_signature in file.read():
                print("⚠️ 结果未变化，未重复写入日志。")
                return

    try:
        with open(log_file, "a", encoding="utf-8") as file:
            file.write(current_log)
        print(f"✅ 结果已追加到日志: {log_file}")

    except Exception as e:
        print(f"⚠️ 保存日志时出错: {e}")

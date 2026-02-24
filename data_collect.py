from bs4 import BeautifulSoup
from typing import Optional, Tuple
import numpy as np
import empty_confirm


class HTMLValueExtractor:
    def __init__(self, file_path: str = "test.html"):
        self.file_path = file_path
        self.soup = None

    def load_and_parse(self) -> BeautifulSoup:
        """加载并解析HTML文件"""
        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                content = file.read()
            self.soup = BeautifulSoup(content, "html.parser")
            return self.soup
        except FileNotFoundError:
            raise ValueError(f"文件 {self.file_path} 未找到")
        except Exception as e:
            raise RuntimeError(f"解析HTML文件失败: {str(e)}")

    @staticmethod
    def find_svg_value(soup: BeautifulSoup,
                       g_id: str,
                       tspan_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        查找SVG中的数值
        返回: (结果值, 错误信息)
        """
        try:
            value_element = soup.find("g", {"id": g_id})
            if not value_element:
                return None, f"未找到目标 <g id='{g_id}'> 元素"

            tspan = value_element.find("tspan", {"id": tspan_id})
            if not tspan:
                return None, f"未找到目标 <tspan id='{tspan_id}'> 元素"

            return tspan.text.strip(), None
        except AttributeError:
            return None, "HTML结构不符合预期"
        except Exception as e:
            return None, f"解析过程中发生异常: {str(e)}"

    def get_value(self, g_id: str, tspan_id: str) -> str:
        """
        完整流程获取值
        返回: 提取到的值字符串
        """
        if not self.soup:
            self.load_and_parse()

        value, error = self.find_svg_value(self.soup, g_id, tspan_id)
        if error:
            raise ValueError(error)
        return value


def init_value():
    specified_values = [37, 101, 38, 102, 103, 104, 105, 106, 41, 107, 42, 108,
                        43, 109, 44, 110, 45, 111, 46, 112, 47, 113, 48, 114,
                        49, 115, 50, 116, 51, 117, 52, 118, 53, 119, 54, 120,
                        55, 121, 122, 123, 124, 125, 58, 126, 59, 127, 60, 128]
    target_ids = []

    # 批量生成并追加到 target_ids
    target_ids.extend([
        (f"Value{num}", f"Value{num}_pbTextEl_Value") for num in specified_values
    ])
    return target_ids


# 使用示例
if __name__ == "__main__":
    try:
        # 初始化提取器
        extractor = HTMLValueExtractor("test.html")
        total_values = []
        for g_id, tspan_id in init_value():
            try:
                value = HTMLValueExtractor().get_value(g_id, tspan_id)
                total_values.append(value)
            except ValueError as e:
                print(f"提取值失败: {str(e)}")

        # 方式一：使用 array_to_dict
        if total_values:
            print("提取结果1:", empty_confirm.array_to_dict(np.array(total_values).reshape(4, 6, 2)))

        # 方式二：分步使用
        extractor.load_and_parse()
        value, err = HTMLValueExtractor.find_svg_value(extractor.soup,
                                                       "Value117",
                                                       "Value117_pbTextEl_Value")
        if err:
            print("提取结果2:", err)
        else:
            print("提取结果2:", value)

    except Exception as e:
        print(f"操作失败: {str(e)}")

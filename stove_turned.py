from bs4 import BeautifulSoup
from typing import Optional, Tuple


class HTMLColorExtractor:
    def __init__(self, file_path: str = "color.html"):
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
    def find_text_fill(soup: BeautifulSoup, text_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        查找 `<text>` 标签的 `fill` 颜色
        返回: (颜色值, 错误信息)
        """
        try:
            text_element = soup.find("text", {"id": text_id})
            if not text_element:
                return None, f"未找到 <text id='{text_id}'> 元素"

            fill_color = text_element.get("fill")
            if not fill_color:
                return None, f"<text id='{text_id}'> 没有 `fill` 颜色属性"

            return fill_color, None
        except AttributeError:
            return None, "HTML结构不符合预期"
        except Exception as e:
            return None, f"解析过程中发生异常: {str(e)}"

    def get_color(self, text_id: str) -> str:
        """
        获取 `<text>` 标签的 `fill` 颜色值
        """
        if not self.soup:
            self.load_and_parse()

        color, error = self.find_text_fill(self.soup, text_id)
        if error:
            raise ValueError(error)
        return color


# **定义磨煤机的 ID 列表**
mill_ids = {
    "1号机组": ["Text59_pbTextEl", "Text58_pbTextEl", "Text57_pbTextEl", "Text60_pbTextEl"],
    "2号机组": ["Text62_pbTextEl", "Text63_pbTextEl", "Text64_pbTextEl", "Text61_pbTextEl"],
    "3号机组": ["Text66_pbTextEl", "Text67_pbTextEl", "Text68_pbTextEl", "Text65_pbTextEl"],
    "4号机组": ["Text70_pbTextEl", "Text71_pbTextEl", "Text72_pbTextEl", "Text69_pbTextEl"]
}


def Color_extract():
    extractor = HTMLColorExtractor("color.html")
    extractor.load_and_parse()  # 只解析一次 HTML

    color_data = {}
    for unit, ids in mill_ids.items():
        color_data[unit] = {}
        for idx, mill_id in enumerate(ids):
            try:
                color = extractor.get_color(mill_id)
                color_data[unit][f"{chr(65 + idx)} 磨"] = color  # A/B/C/D 磨
            except ValueError as e:
                color_data[unit][f"{chr(65 + idx)} 磨"] = str(e)  # 记录错误信息
        return color_data


# **使用示例**
if __name__ == "__main__":
    extractor = HTMLColorExtractor("color.html")
    extractor.load_and_parse()  # 只解析一次 HTML

    color_data = {}
    for unit, ids in mill_ids.items():
        color_data[unit] = {}
        for idx, mill_id in enumerate(ids):
            try:
                color = extractor.get_color(mill_id)
                color_data[unit][f"{chr(65 + idx)} 磨"] = color  # A/B/C/D 磨
            except ValueError as e:
                color_data[unit][f"{chr(65 + idx)} 磨"] = str(e)  # 记录错误信息

    # **打印磨煤机颜色信息**
    for unit, mills in color_data.items():
        print(f"\n{unit}:")
        for mill, color in mills.items():
            print(f"  {mill}: {color}")
    print(color_data)

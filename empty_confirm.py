import numpy as np
from collections import defaultdict
from datetime import datetime


class Previous_records_manger:
    def __init__(self):
        self.previous_records = defaultdict(dict)  # 直接存储 dict，避免 list 嵌套
        self.low_threshold = 4.0  # 低料位阈值
        self.second_threshold = 6.0  # 二类标记阈值

    @staticmethod
    def _to_float(value):
        """安全转换为 float，失败返回 None"""
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def container_marked(self, data_dict):
        """标记低料位仓位，避免重复记录"""
        for boiler, containers in data_dict.items():
            for container, heights in containers.items():
                heights = [self._to_float(h) for h in heights if self._to_float(h) is not None]
                if any(h < self.low_threshold for h in heights):
                    # 仅在数值变化时更新记录
                    if container not in self.previous_records[boiler] or self.previous_records[boiler][container] != heights:
                        self.previous_records[boiler][container] = heights
        return self.previous_records

    def double_marking(self, new_data):
        """执行二类标记检测，检查仓位是否烧空"""
        result = defaultdict(dict)

        for boiler, containers in new_data.items():
            if boiler not in self.previous_records:
                continue

            for container, current_heights in containers.items():
                heights = [self._to_float(h) for h in current_heights if self._to_float(h) is not None]
                history_values = self.previous_records[boiler].get(container, [])

                if heights and history_values and heights != history_values:
                    mark_type = "烧空仓标记" if all(h > self.second_threshold for h in heights) else "非空仓"
                    result[boiler][container] = {"标记类型": mark_type, "当前值": heights, "历史值": history_values}

        # 清理空记录
        self.previous_records = {k: v for k, v in self.previous_records.items() if v}
        return dict(result)


def array_to_dict(total_values):
    """转换原始矩阵数据为字典格式"""
    total_values = np.reshape(total_values, (4, 6, 2)).astype(float)  # ✅ 直接转换
    return {
        f"#{i + 5}炉": {f"{chr(j + 65)}仓": list(height) for j, height in enumerate(boiler)}
        for i, boiler in enumerate(total_values)
    }


Array2Dict = array_to_dict  # 别名，供 PIVdata2 调用

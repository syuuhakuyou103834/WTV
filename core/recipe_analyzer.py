#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recipe分析模块
用于分析载台运动速度Recipe文件的统计信息
"""

import os
import pandas as pd


class RecipeAnalyzer:
    """Recipe分析器"""

    def __init__(self):
        self.recipe_rows = 0
        self.etch_time_seconds = 0.0
        self.etch_time_formatted = "0分0秒"

    def analyze_recipe_file(self, recipe_file_path):
        """
        分析Recipe文件并计算统计信息

        Args:
            recipe_file_path: Recipe文件路径

        Returns:
            tuple: (recipe_rows, etch_time_formatted, etch_time_seconds)
        """
        try:
            if not os.path.exists(recipe_file_path):
                return (0, "0分0秒", 0.0)

            # 读取Recipe文件
            df = pd.read_csv(recipe_file_path)

            if len(df) < 2:
                return (0, "0分0秒", 0.0)

            # 计算Recipe行数（去掉表头和最后一行）
            self.recipe_rows = len(df) - 2
            if self.recipe_rows < 0:
                self.recipe_rows = 0

            # 计算刻蚀时间
            self.etch_time_seconds = self._calculate_etch_time(df)
            self.etch_time_formatted = self._format_time(self.etch_time_seconds)

            return (self.recipe_rows, self.etch_time_formatted, self.etch_time_seconds)

        except Exception as e:
            print(f"分析Recipe文件失败: {str(e)}")
            return (0, "0分0秒", 0.0)

    def _calculate_etch_time(self, df):
        """
        计算刻蚀时间

        Args:
            df: Recipe数据的DataFrame

        Returns:
            float: 刻蚀时间（秒）
        """
        if len(df) < 3:
            return 0.0

        total_time = 0.0

        # 假设列名，根据您的描述调整
        y_pos_col = "Y-Position"
        y_speed_col = "Y-speed"

        # 尝试找到对应的列（处理列名可能的情况）
        y_pos_col = self._find_column(df, ["Y-Position", "Y Position", "y_position", "y_position"])
        y_speed_col = self._find_column(df, ["Y-speed", "Y Speed", "y_speed", "y_speed"])

        if y_pos_col is None or y_speed_col is None:
            print(f"警告: 未找到Y-Position或Y-speed列")
            print(f"可用列名: {list(df.columns)}")
            return 0.0

        # 计算除表头(第1行)和最后一行之外的所有行的停留时间
        for i in range(1, len(df) - 1):  # 从第2行到倒数第2行
            try:
                current_y_pos = float(df.iloc[i][y_pos_col])
                next_y_pos = float(df.iloc[i + 1][y_pos_col])
                current_y_speed = float(df.iloc[i][y_speed_col])

                # 计算停留时间
                if current_y_speed == 0:
                    dwell_time = 0.1  # Y-speed为0时直接记为0.1s
                else:
                    distance = abs(next_y_pos - current_y_pos)
                    dwell_time = distance / current_y_speed

                total_time += dwell_time

            except (ValueError, KeyError, IndexError) as e:
                print(f"处理第{i+1}行时出错: {str(e)}")
                continue

        return total_time

    def _find_column(self, df, possible_names):
        """
        在DataFrame中查找列名

        Args:
            df: DataFrame
            possible_names: 可能的列名列表

        Returns:
            str: 找到的列名，如果没找到返回None
        """
        for name in possible_names:
            if name in df.columns:
                return name

        # 尝试不区分大小写
        for name in possible_names:
            for col in df.columns:
                if col.lower() == name.lower():
                    return col

        return None

    def _format_time(self, seconds):
        """
        格式化时间为 分:秒 格式

        Args:
            seconds: 秒数

        Returns:
            str: 格式化后的时间字符串
        """
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        return f"{minutes}分{remaining_seconds}秒"

    def get_recipe_statistics(self):
        """
        获取Recipe统计信息

        Returns:
            dict: 包含recipe行数和刻蚀时间的字典
        """
        return {
            'recipe_rows': self.recipe_rows,
            'etch_time_seconds': self.etch_time_seconds,
            'etch_time_formatted': self.etch_time_formatted
        }


def analyze_recipe_file(file_path):
    """
    便捷函数：分析单个Recipe文件

    Args:
        file_path: Recipe文件路径

    Returns:
        tuple: (recipe_rows, etch_time_formatted, etch_time_seconds)
    """
    analyzer = RecipeAnalyzer()
    return analyzer.analyze_recipe_file(file_path)


if __name__ == "__main__":
    # 测试代码
    test_file = "1925_1120BeamProfile_peak189_ac70_Stage_Movement_Instruction_Recipe.csv"

    if os.path.exists(test_file):
        print(f"分析文件: {test_file}")
        recipe_rows, etch_time_formatted, etch_time_seconds = analyze_recipe_file(test_file)
        print(f"Recipe行数: {recipe_rows}")
        print(f"刻蚀时间: {etch_time_formatted}")
        print(f"刻蚀时间(秒): {etch_time_seconds}")
    else:
        print(f"测试文件不存在: {test_file}")
        print("请在当前目录放置测试文件进行测试")
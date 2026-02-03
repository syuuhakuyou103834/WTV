#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟日志记录模块
用于生成和管理晶圆模拟过程的详细记录
"""

import os
import csv
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from pathlib import Path


class SimulationLogger:
    """模拟日志记录器"""

    def __init__(self):
        # 日志文件的28个字段定义
        self.log_fields = [
            # 基本信息字段
            ("Date", "当前日期"),
            ("Time", "当前时间"),
            ("Grid_size(mm)", "模拟使用的模拟网格尺寸"),
            ("Resolution(mm/pixel)", "模拟使用的分辨率"),
            ("WF_size(mm)", "晶圆直径"),
            ("Target(nm)", "目标膜厚"),
            ("Stage_center_X", "载台中心的x坐标"),
            ("Stage_center_Y", "载台中心的Y坐标"),
            ("y-step", "y-step步长"),
            ("Transition_area_Width(mm)", "过渡区宽度"),
            ("Recipe_Length(nm)", "Recipe截取范围"),
            ("Result_Judge_Criteria(%)", "验算均一性阈值"),
            ("Plural_Scan_Judge_Criteria(nm)", "倍速多次扫描判定阈值"),

            # 文件和模拟过程字段
            ("WF_No.", "用户选择的初始膜厚数据文件的文件名"),
            ("simulation_time", "达到验算均一性阈值标准共模拟的次数"),
            ("error_deleted_time", "异常值剔除的次数"),
            ("Deleted_points", "总共剔除的异常点的个数"),

            # 初始膜厚统计字段
            ("Origin_Max(nm)", "初始膜厚的最大值"),
            ("Origin_Min(nm)", "初始膜厚的最小值"),
            ("Origin_Average(nm)", "初始膜厚的平均值"),
            ("Origin_Range(nm)", "初始膜厚的范围"),
            ("Origin_Uniformity(%)", "初始膜厚的均一性"),

            # 模拟结果统计字段
            ("Simulated_Max(nm)", "模拟结果的最大值"),
            ("Simulated_Min(nm)", "模拟结果的最小值"),
            ("Simulated_Average(nm)", "模拟结果的平均值"),
            ("Simulated_Range(nm)", "模拟结果的范围"),
            ("Simulated_Uniformity(%)", "模拟结果的均一性"),

            # 最终结果字段
            ("Ave_Etching_amount(nm)", "刻蚀量的平均值"),
            ("Plural_Scan_Time", "倍速多次扫描次数"),
            ("Etching_time(s)", "刻蚀时间")
        ]

    def generate_simulation_log(self,
                              output_directory: str,
                              simulation_data: Dict[str, Any],
                              etching_time_seconds: float = None) -> str:
        """
        生成模拟日志CSV文件

        Args:
            output_directory: 输出目录路径
            simulation_data: 模拟数据字典，包含所有需要记录的信息
            etching_time_seconds: 刻蚀时间（秒），如果为None则不包含此字段

        Returns:
            str: 生成的日志文件路径
        """
        try:
            # 确保输出目录存在
            os.makedirs(output_directory, exist_ok=True)

            # 从文件名提取WF编号
            wf_number = self._extract_wf_number(simulation_data.get('file_name', ''))

            # 生成日志数据
            log_data = self._prepare_log_data(simulation_data, wf_number, etching_time_seconds)

            # 生成日志文件名
            log_filename = f"{wf_number}_simulation_log.csv"
            log_file_path = os.path.join(output_directory, log_filename)

            # 写入CSV文件
            self._write_log_to_csv(log_file_path, log_data)

            print(f"模拟日志已生成: {log_file_path}")
            return log_file_path

        except Exception as e:
            print(f"生成模拟日志失败: {str(e)}")
            raise

    def _extract_wf_number(self, file_name: str) -> str:
        """
        从文件名中提取WF编号

        Args:
            file_name: 文件名

        Returns:
            str: WF编号，如果无法提取则返回"unknown"
        """
        try:
            # 尝试从文件名中提取数字（如2711）
            import re
            match = re.search(r'(\d+)', file_name)
            if match:
                return match.group(1)
            else:
                return "unknown"
        except Exception:
            return "unknown"

    def _prepare_log_data(self, simulation_data: Dict[str, Any],
                         wf_number: str, etching_time_seconds: float = None) -> Dict[str, str]:
        """
        准备日志数据

        Args:
            simulation_data: 模拟数据字典
            wf_number: WF编号
            etching_time_seconds: 刻蚀时间

        Returns:
            Dict: 格式化的日志数据
        """
        # 获取当前日期和时间
        now = datetime.now()
        current_date = now.strftime("%Y%m%d")
        current_time = now.strftime("%H:%M:%S")

        # 格式化数值，保留2位小数
        def format_value(value, default=0.0):
            if value is None:
                return f"{default:.2f}"
            try:
                return f"{float(value):.2f}"
            except (ValueError, TypeError):
                return f"{default:.2f}"

        # 计算统计信息
        origin_stats = simulation_data.get('origin_statistics', {})
        simulated_stats = simulation_data.get('simulated_statistics', {})

        # 获取刻蚀量统计信息
        etch_stats = simulation_data.get('etching_statistics', {})
        etching_amount_avg = float(etch_stats.get('average', 0.0))

        # 准备基本日志数据
        log_data = {
            # 基本信息
            "Date": current_date,
            "Time": current_time,
            "Grid_size(mm)": format_value(simulation_data.get('grid_size', 240)),
            "Resolution(mm/pixel)": format_value(simulation_data.get('resolution', 1.0)),
            "WF_size(mm)": format_value(simulation_data.get('wf_size', 150)),
            "Target(nm)": format_value(simulation_data.get('target_thickness', 0)),
            "Stage_center_X": format_value(simulation_data.get('stage_center_x', 0.0)),
            "Stage_center_Y": format_value(simulation_data.get('stage_center_y', 0.0)),
            "y-step": str(simulation_data.get('y_step', 2)),
            "Transition_area_Width(mm)": format_value(simulation_data.get('transition_width', 50)),
            "Recipe_Length(nm)": format_value(simulation_data.get('recipe_range', 160)),
            "Result_Judge_Criteria(%)": format_value(simulation_data.get('uniformity_threshold', 0.5)),
            "Plural_Scan_Judge_Criteria(nm)": format_value(simulation_data.get('speed_threshold', 140.0)),

            # 文件和模拟过程
            "WF_No.": wf_number,
            "simulation_time": str(simulation_data.get('simulation_count', 1)),
            "error_deleted_time": str(simulation_data.get('outlier_removal_count', 0)),
            "Deleted_points": str(simulation_data.get('total_removed_points', 0)),

            # 初始膜厚统计
            "Origin_Max(nm)": format_value(origin_stats.get('max', 0.0)),
            "Origin_Min(nm)": format_value(origin_stats.get('min', 0.0)),
            "Origin_Average(nm)": format_value(origin_stats.get('average', 0.0)),
            "Origin_Range(nm)": format_value(origin_stats.get('range', 0.0)),
            "Origin_Uniformity(%)": format_value(origin_stats.get('uniformity', 0.0)),

            # 刻蚀后膜厚统计
            "Simulated_Max(nm)": format_value(simulated_stats.get('max', 0.0)),
            "Simulated_Min(nm)": format_value(simulated_stats.get('min', 0.0)),
            "Simulated_Average(nm)": format_value(simulated_stats.get('average', 0.0)),
            "Simulated_Range(nm)": format_value(simulated_stats.get('range', 0.0)),
            "Simulated_Uniformity(%)": format_value(simulated_stats.get('uniformity', 0.0)),

            # 最终结果
            "Ave_Etching_amount(nm)": format_value(etching_amount_avg),
            "Plural_Scan_Time": str(simulation_data.get('plural_scan_time', 1))
        }

        # 添加刻蚀时间（如果提供）
        if etching_time_seconds is not None:
            log_data["Etching_time(s)"] = format_value(etching_time_seconds)

        return log_data

    def _write_log_to_csv(self, log_file_path: str, log_data: Dict[str, str]):
        """
        将日志数据写入CSV文件

        Args:
            log_file_path: 日志文件路径
            log_data: 日志数据字典
        """
        try:
            with open(log_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # 写入表头和数据
                for field_name, field_value in log_data.items():
                    writer.writerow([field_name, field_value])

        except Exception as e:
            print(f"写入CSV文件失败: {str(e)}")
            raise

    def read_initial_thickness_stats(self, thickness_file_path: str) -> Dict[str, float]:
        """
        读取初始膜厚数据并计算统计信息

        Args:
            thickness_file_path: 膜厚数据文件路径

        Returns:
            Dict: 统计信息字典
        """
        try:
            # 读取膜厚数据文件
            df = pd.read_csv(thickness_file_path)

            # 专门查找膜厚相关的列（排除坐标列）
            thickness_columns = []
            for col in df.columns:
                col_lower = col.lower()
                # 排除坐标列，查找膜厚数据列
                if (not any(coord in col_lower for coord in ['x', 'y', 'row', 'col', 'index']) and
                    any(thickness in col_lower for thickness in ['thickness', '膜厚', 'nm', 'value'])):
                    thickness_columns.append(col)

            # 如果没有找到明确的膜厚列，使用第一列数值数据（通常第一列是坐标，第二列开始是膜厚）
            if not thickness_columns:
                for col in df.columns[1:]:  # 跳过第一列（通常是坐标）
                    try:
                        pd.to_numeric(df[col])
                        thickness_columns.append(col)
                        break  # 只取第一个数值列
                    except (ValueError, TypeError):
                        continue

            if not thickness_columns:
                raise ValueError("文件中没有找到膜厚数据列")

            # 提取膜厚数据
            all_values = []
            for col in thickness_columns:
                values = pd.to_numeric(df[col], errors='coerce').dropna()
                all_values.extend(values.tolist())

            if not all_values:
                raise ValueError("膜厚数据列中没有有效数值")

            # 计算统计信息
            values_array = pd.Series(all_values)
            stats = {
                'max': float(values_array.max()),
                'min': float(values_array.min()),
                'average': float(values_array.mean()),
                'range': float(values_array.max() - values_array.min()),
                'count': int(len(values_array))
            }

            # 计算均一性：U% = Range / (2 * Average)
            if stats['average'] > 0:
                stats['uniformity'] = float(stats['range'] / (2 * stats['average']) * 100)
            else:
                stats['uniformity'] = 0.0

            return stats

        except Exception as e:
            print(f"读取初始膜厚统计信息失败: {str(e)}")
            # 返回默认值
            return {
                'max': 0.0, 'min': 0.0, 'average': 0.0,
                'range': 0.0, 'uniformity': 0.0, 'count': 0
            }

    def read_simulation_results_stats(self, results_file_path: str) -> Dict[str, float]:
        """
        读取刻蚀后膜厚统计信息

        Args:
            results_file_path: 刻蚀后膜厚结果文件路径

        Returns:
            Dict: 统计信息字典
        """
        try:
            # 读取刻蚀后膜厚结果文件
            df = pd.read_csv(results_file_path)

            # 专门查找刻蚀后膜厚相关的列（排除坐标列）
            result_columns = []
            for col in df.columns:
                col_lower = col.lower()
                # 排除坐标列，查找结果数据列
                if (not any(coord in col_lower for coord in ['x', 'y', 'row', 'col', 'index']) and
                    any(result in col_lower for result in ['result', 'validated', 'thickness', '膜厚', 'nm'])):
                    result_columns.append(col)

            # 如果没有找到明确的结果列，使用第一列数值数据（跳过坐标列）
            if not result_columns:
                for col in df.columns[1:]:  # 跳过第一列（通常是坐标）
                    try:
                        pd.to_numeric(df[col])
                        result_columns.append(col)
                        break  # 只取第一个数值列
                    except (ValueError, TypeError):
                        continue

            if not result_columns:
                raise ValueError("结果文件中没有找到刻蚀后膜厚数据列")

            # 提取刻蚀后膜厚数据
            all_values = []
            for col in result_columns:
                values = pd.to_numeric(df[col], errors='coerce').dropna()
                all_values.extend(values.tolist())

            if not all_values:
                raise ValueError("刻蚀后膜厚数据列中没有有效数值")

            # 计算统计信息
            values_array = pd.Series(all_values)
            stats = {
                'max': float(values_array.max()),
                'min': float(values_array.min()),
                'average': float(values_array.mean()),
                'range': float(values_array.max() - values_array.min()),
                'count': int(len(values_array))
            }

            # 计算均一性：U% = Range / (2 * Average)
            if stats['average'] > 0:
                stats['uniformity'] = float(stats['range'] / (2 * stats['average']) * 100)
            else:
                stats['uniformity'] = 0.0

            return stats

        except Exception as e:
            print(f"读取刻蚀后膜厚统计信息失败: {str(e)}")
            # 返回默认值
            return {
                'max': 0.0, 'min': 0.0, 'average': 0.0,
                'range': 0.0, 'uniformity': 0.0, 'count': 0
            }

    def get_etching_amount_stats_from_processor(self, etching_processor) -> Dict[str, float]:
        """
        从刻蚀处理器获取刻蚀量统计信息

        Args:
            etching_processor: 刻蚀处理器实例

        Returns:
            Dict: 刻蚀量统计信息字典
        """
        try:
            if hasattr(etching_processor, 'calculate_etching_amount_statistics'):
                stats = etching_processor.calculate_etching_amount_statistics()
                if stats:
                    return {
                        'max': float(stats.get('max', 0.0)),
                        'min': float(stats.get('min', 0.0)),
                        'average': float(stats.get('mean', 0.0)),
                        'range': float(stats.get('range', 0.0)),
                        'uniformity': float(stats.get('uniformity', 0.0)),
                        'count': int(stats.get('count', 0))
                    }

            # 如果没有直接的刻蚀量统计方法，返回默认值
            return {
                'max': 0.0, 'min': 0.0, 'average': 0.0,
                'range': 0.0, 'uniformity': 0.0, 'count': 0
            }

        except Exception as e:
            print(f"获取刻蚀量统计失败: {str(e)}")
            # 返回默认值
            return {
                'max': 0.0, 'min': 0.0, 'average': 0.0,
                'range': 0.0, 'uniformity': 0.0, 'count': 0
            }

    def _read_etching_amount_from_files(self, output_directory: str) -> Dict[str, float]:
        """
        从输出文件读取刻蚀量统计信息

        Args:
            output_directory: 输出目录

        Returns:
            Dict: 刻蚀量统计信息字典
        """
        try:
            import glob
            # 尝试找到刻蚀量相关的文件
            etch_files = []
            for pattern in ["*etch*amount*.csv", "*刻蚀量*.csv", "*etching*.csv"]:
                etch_files.extend(glob.glob(os.path.join(output_directory, pattern)))

            if etch_files:
                # 使用最新的刻蚀量文件
                latest_etch_file = max(etch_files, key=os.path.getctime)
                df = pd.read_csv(latest_etch_file)

                # 查找刻蚀量数据列
                etch_columns = []
                for col in df.columns:
                    col_lower = col.lower()
                    if (not any(coord in col_lower for coord in ['x', 'y', 'row', 'col', 'index']) and
                        any(etch in col_lower for etch in ['etch', 'amount', '刻蚀', 'nm'])):
                        etch_columns.append(col)

                if not etch_columns:
                    # 如果没有找到明确的刻蚀量列，使用第一个数值列（跳过坐标）
                    for col in df.columns[1:]:
                        try:
                            pd.to_numeric(df[col])
                            etch_columns.append(col)
                            break
                        except (ValueError, TypeError):
                            continue

                if etch_columns:
                    all_values = []
                    for col in etch_columns:
                        values = pd.to_numeric(df[col], errors='coerce').dropna()
                        all_values.extend(values.tolist())

                    if all_values:
                        values_array = pd.Series(all_values)
                        return {
                            'max': float(values_array.max()),
                            'min': float(values_array.min()),
                            'average': float(values_array.mean()),
                            'range': float(values_array.max() - values_array.min()),
                            'uniformity': float((values_array.max() - values_array.min()) / (2 * values_array.mean()) * 100) if values_array.mean() > 0 else 0.0,
                            'count': int(len(values_array))
                        }

            # 如果无法读取刻蚀量文件，返回默认值
            return {
                'max': 0.0, 'min': 0.0, 'average': 0.0,
                'range': 0.0, 'uniformity': 0.0, 'count': 0
            }

        except Exception as e:
            print(f"从文件读取刻蚀量统计失败: {str(e)}")
            return {
                'max': 0.0, 'min': 0.0, 'average': 0.0,
                'range': 0.0, 'uniformity': 0.0, 'count': 0
            }

    def print_log_template(self):
        """打印日志字段模板，供参考"""
        print("=== 模拟日志字段模板 ===")
        print("序号 | 字段名 | 说明")
        print("-" * 60)
        for i, (field_name, description) in enumerate(self.log_fields, 1):
            print(f"{i:2d} | {field_name:<25} | {description}")


# 便捷函数
def create_simulation_logger() -> SimulationLogger:
    """创建模拟日志记录器实例"""
    return SimulationLogger()


def generate_simulation_log(output_directory: str,
                          simulation_data: Dict[str, Any],
                          etching_time_seconds: float = None) -> str:
    """
    便捷函数：生成模拟日志

    Args:
        output_directory: 输出目录路径
        simulation_data: 模拟数据字典
        etching_time_seconds: 刻蚀时间（秒）

    Returns:
        str: 生成的日志文件路径
    """
    logger = SimulationLogger()
    return logger.generate_simulation_log(output_directory, simulation_data, etching_time_seconds)


if __name__ == "__main__":
    # 测试代码
    print("测试模拟日志记录器...")

    # 打印字段模板
    logger = SimulationLogger()
    logger.print_log_template()

    # 模拟测试数据
    test_simulation_data = {
        'file_name': '2711.csv',
        'grid_size': 240,
        'resolution': 1.0,
        'wf_size': 150,
        'target_thickness': 1800,
        'stage_center_x': 0.0,
        'stage_center_y': 0.0,
        'y_step': 2,
        'transition_width': 50,
        'recipe_range': 160,
        'uniformity_threshold': 0.5,
        'simulation_count': 3,
        'outlier_removal_count': 2,
        'total_removed_points': 3,
        'origin_statistics': {
            'max': 1957.4,
            'min': 1795.9,
            'average': 1893.4,
            'range': 161.5,
            'uniformity': 4.27
        },
        'simulated_statistics': {
            'max': 1803.4,
            'min': 1794.3,
            'average': 1799.6,
            'range': 9.1,
            'uniformity': 0.25
        }
    }

    # 测试生成日志
    output_dir = "test_logs"
    log_file = logger.generate_simulation_log(output_dir, test_simulation_data, 367.0)

    print(f"\n测试日志已生成: {log_file}")
    print("测试完成！")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动数据优化模块
用于处理刻蚀模拟中的异常值检测和数据优化流程
"""

import os
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import QMessageBox


class AutomaticDataOptimizer:
    """自动数据优化器"""

    def __init__(self, main_window, uniformity_threshold):
        """
        初始化数据优化器

        Args:
            main_window: 主窗口对象
            uniformity_threshold: 均一性阈值
        """
        self.main_window = main_window
        self.uniformity_threshold = uniformity_threshold
        self.all_removed_indices = []

    def show_simulation_complete_dialog(self, results, unity_msg, validated_stats, callback):
        """
        显示模拟完成对话框，包含数据优化选项

        Args:
            results: 模拟结果
            unity_msg: 均一性消息
            validated_stats: 验算统计信息
            callback: 回调函数，用于重新模拟
        """
        if validated_stats and 'uniformity' in validated_stats:
            unity = validated_stats['uniformity']
            if unity > self.uniformity_threshold:
                # 均一性不达标，询问用户是否要修改数据
                reply = QMessageBox.question(
                    self.main_window,
                    "均一性不达标",
                    f"刻蚀模拟完成！\n\n"
                    f"验算均一性: {unity:.2f}% ❌ (阈值: {self.uniformity_threshold:.2f}%)\n\n"
                    f"当前模拟结果未达到设定的均一性要求。\n"
                    f"是否要修改原膜厚数据并重新进行模拟？\n\n"
                    f"选择【是】将自动检测并剔除异常值来改善均一性\n"
                    f"选择【否】将保存当前模拟结果",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    # 开始异常值处理和自动迭代流程
                    self.start_automatic_data_optimization(results, callback)
                    return None  # 不显示标准的结果对话框

        # 返回标准完成信息
        return (f"刻蚀模拟完成!{unity_msg}\n"
                f"- 初始膜厚图: {os.path.basename(results['initial_thickness_map'])}\n"
                f"- 刻蚀深度图: {os.path.basename(results['etching_depth_map'])}\n"
                f"- 验算膜厚图: {os.path.basename(results['validated_thickness_map'])}\n"
                f"- 停留时间图: {os.path.basename(results['dwell_time_map'])}\n"
                f"- 速度分布图: {os.path.basename(results['velocity_map'])}\n"
                f"- 轨迹文件: {os.path.basename(results['stage_recipe'])}")

    def start_automatic_data_optimization(self, results, callback):
        """开始自动数据优化流程"""
        try:
            # 获取原始文件路径
            original_file = results.get('original_etching_file')
            if not original_file or not os.path.exists(original_file):
                QMessageBox.critical(self.main_window, "错误", "找不到原始膜厚数据文件")
                return

            # 读取原始数据
            original_data = self.read_thickness_data(original_file)
            if original_data is None:
                QMessageBox.critical(self.main_window, "错误", "无法读取原始膜厚数据文件")
                return

            # 保存真正的原始文件路径和原始数据量（不会被后续修改）
            self.true_original_file = original_file
            self.true_original_count = len(original_data)
            # 初始化所有已剔除点的索引记录
            self.all_removed_indices = []

            # 保存回调函数
            self.simulation_callback = callback

            # 开始异常值剔除流程
            self.outlier_removal_stage(original_data, original_file, results, iteration=1)

        except Exception as e:
            QMessageBox.critical(self.main_window, "错误", f"启动自动优化流程失败: {str(e)}")

    def read_thickness_data(self, file_path):
        """读取膜厚数据文件"""
        try:
            df = pd.read_csv(file_path)
            if len(df.columns) >= 3:
                # 假设列名为 [x, y, thickness] 或类似
                data = df.iloc[:, :3].values
                return data
            else:
                return None
        except Exception as e:
            self.main_window.update_status_message(f"读取数据文件失败: {str(e)}", "error")
            return None

    def detect_outliers_iqr(self, thickness_values):
        """使用IQR方法检测异常值"""
        if len(thickness_values) < 4:
            return np.array([]), None, None  # 数据太少，无法检测异常值

        q1 = np.percentile(thickness_values, 25)
        q3 = np.percentile(thickness_values, 75)
        iqr = q3 - q1

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outlier_mask = (thickness_values < lower_bound) | (thickness_values > upper_bound)
        outlier_indices = np.where(outlier_mask)[0]

        return outlier_indices, lower_bound, upper_bound

    def outlier_removal_stage(self, current_data, original_file, initial_results, iteration=1):
        """异常值剔除阶段"""
        if iteration > 20:  # 最大20轮异常值剔除
            reply = QMessageBox.question(
                self.main_window,
                "达到最大迭代次数",
                f"已进行{iteration-1}轮异常值剔除，仍未达到均一性要求。\n\n"
                f"是否尝试从最小值开始逐步剔除？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self.minimum_value_removal_stage(current_data, original_file, initial_results, outlier_rounds=iteration)
            else:
                self.save_current_results_and_exit(initial_results)
            return

        # 检测异常值
        thickness_values = current_data[:, 2]
        outlier_indices, lower_bound, upper_bound = self.detect_outliers_iqr(thickness_values)

        if len(outlier_indices) == 0:
            # 没有异常值了，询问是否从最小值开始剔除
            reply = QMessageBox.question(
                self.main_window,
                "无异常值",
                f"当前数据已不存在基于四分位距的异常值。\n\n"
                f"是否从最小值开始逐步剔除以进一步改善均一性？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self.minimum_value_removal_stage(current_data, original_file, initial_results, outlier_rounds=iteration)
            else:
                self.save_current_results_and_exit(initial_results)
            return

        # 检查剔除异常值后的数据量
        remaining_count = len(current_data) - len(outlier_indices)
        # 使用保存的原始数据量，确保始终基于真正的原始数据
        original_count = self.true_original_count

        if remaining_count < original_count * 0.8:
            QMessageBox.warning(self.main_window, "数据量不足",
                f"剔除{len(outlier_indices)}个异常值后，剩余数据点数({remaining_count})\n"
                f"将少于原始数据的80%({int(original_count * 0.8)})，无法继续剔除。\n\n"
                f"将保存当前模拟结果。")
            self.save_current_results_and_exit(initial_results)
            return

        # 显示将要剔除的异常值信息
        outlier_thickness = thickness_values[outlier_indices]
        info_msg = f"第{iteration}轮异常值检测结果：\n\n"
        info_msg += f"检测到 {len(outlier_indices)} 个异常值：\n"
        info_msg += f"- 异常值范围: {outlier_thickness.min():.2f} - {outlier_thickness.max():.2f} nm\n"
        info_msg += f"- 正常值范围: {lower_bound:.2f} - {upper_bound:.2f} nm\n"
        info_msg += f"- 剔除后剩余点数: {remaining_count} / {original_count} ({remaining_count/original_count*100:.1f}%)\n\n"
        info_msg += f"是否执行此次剔除并重新模拟？"

        reply = QMessageBox.question(
            self.main_window,
            f"第{iteration}轮异常值剔除",
            info_msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.No:
            self.save_current_results_and_exit(initial_results)
            return

        # 执行异常值剔除
        mask = np.ones(len(current_data), dtype=bool)
        mask[outlier_indices] = False
        cleaned_data = current_data[mask]

        # 记录已剔除的索引
        self.all_removed_indices.extend(outlier_indices.tolist())

        # 保存修改后的数据
        new_file_path = self.generate_optimized_filename(original_file, iteration)
        success = self.save_thickness_data(cleaned_data, new_file_path)

        if not success:
            QMessageBox.critical(self.main_window, "保存失败", "无法保存修改后的数据文件")
            self.save_current_results_and_exit(initial_results)
            return

        # 更新状态并开始新的模拟
        self.main_window.update_status_message(
            f"已剔除{len(outlier_indices)}个异常值，保存为 {os.path.basename(new_file_path)}，开始重新模拟...")

        # 使用新文件进行模拟
        if self.simulation_callback:
            self.simulation_callback(new_file_path, cleaned_data, iteration)

    def minimum_value_removal_stage(self, current_data, original_file, initial_results, removed_min_count=0):
        """最小值剔除阶段"""
        max_min_removals = 50  # 最大50个最小值剔除
        if removed_min_count >= max_min_removals:
            QMessageBox.information(self.main_window, "达到最大剔除次数",
                f"已剔除{removed_min_count}个最小值，仍未达到均一性要求。\n\n"
                f"将保存当前模拟结果。")
            self.save_current_results_and_exit(initial_results)
            return

        # 检查数据量
        # 使用保存的原始数据量，确保始终基于真正的原始数据
        original_count = self.true_original_count

        if len(current_data) < original_count * 0.8:
            QMessageBox.warning(self.main_window, "数据量不足",
                f"当前数据点数({len(current_data)})已少于原始数据的80%。\n\n"
                f"无法继续剔除，将保存当前模拟结果。")
            self.save_current_results_and_exit(initial_results)
            return

        if len(current_data) == 0:
            QMessageBox.warning(self.main_window, "无数据", "数据已全部剔除，无法继续。")
            self.save_current_results_and_exit(initial_results)
            return

        # 找到最小值
        thickness_values = current_data[:, 2]
        min_index = np.argmin(thickness_values)
        min_thickness = thickness_values[min_index]
        min_coords = current_data[min_index, :2]

        # 计算总剔除点数
        total_removed = len(self.all_removed_indices) + removed_min_count

        # 询问是否剔除最小值
        info_msg = f"最小值剔除进度：\n\n"
        info_msg += f"当前最小值: {min_thickness:.2f} nm (位置: {min_coords[0]:.1f}, {min_coords[1]:.1f})\n"
        info_msg += f"已剔除最小值个数: {removed_min_count}\n"
        info_msg += f"总共剔除点数: {total_removed} / {original_count} ({total_removed/original_count*100:.1f}%)\n"
        info_msg += f"剩余数据点数: {len(current_data)} / {original_count} ({len(current_data)/original_count*100:.1f}%)\n\n"
        info_msg += f"是否剔除当前最小值并重新模拟？"

        reply = QMessageBox.question(
            self.main_window,
            f"最小值剔除 (第{removed_min_count + 1}个)",
            info_msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.No:
            self.save_current_results_and_exit(initial_results)
            return

        # 剔除最小值
        mask = np.ones(len(current_data), dtype=bool)
        mask[min_index] = False
        new_data = current_data[mask]

        # 保存修改后的数据
        new_file_path = self.generate_min_removed_filename(original_file, removed_min_count + 1, outlier_rounds)
        success = self.save_thickness_data(new_data, new_file_path)

        if not success:
            QMessageBox.critical(self.main_window, "保存失败", "无法保存修改后的数据文件")
            self.save_current_results_and_exit(initial_results)
            return

        # 更新状态并开始新的模拟
        self.main_window.update_status_message(
            f"已剔除最小值 {min_thickness:.2f}nm，保存为 {os.path.basename(new_file_path)}，开始重新模拟...")

        # 使用新文件进行模拟
        if self.simulation_callback:
            self.simulation_callback(new_file_path, new_data, f"min_removed_{removed_min_count + 1}_outlier_{outlier_rounds}")

    def generate_optimized_filename(self, original_file, iteration):
        """生成优化后的文件名"""
        # 使用真正的原始文件而不是当前处理文件
        base_file = self.true_original_file if hasattr(self, 'true_original_file') else original_file
        base_name = os.path.splitext(os.path.basename(base_file))[0]
        directory = os.path.dirname(base_file)
        new_filename = f"{base_name}_error_deleted_{iteration}_time.csv"
        return os.path.join(directory, new_filename)

    def generate_min_removed_filename(self, original_file, min_count, outlier_rounds=0):
        """生成最小值剔除后的文件名"""
        # 使用真正的原始文件而不是当前处理文件
        base_file = self.true_original_file if hasattr(self, 'true_original_file') else original_file
        base_name = os.path.splitext(os.path.basename(base_file))[0]
        directory = os.path.dirname(base_file)
        
        if outlier_rounds > 0:
            # 如果已经进行了异常值剔除，使用组合命名
            new_filename = f"{base_name}_error_deleted_{outlier_rounds}_time_min_removed_{min_count}.csv"
        else:
            # 如果没有进行异常值剔除，使用简单命名
            new_filename = f"{base_name}_min_removed_{min_count}.csv"
        
        return os.path.join(directory, new_filename)

    def save_thickness_data(self, data, file_path):
        """保存膜厚数据到文件"""
        try:
            df = pd.DataFrame(data, columns=['x', 'y', 'thickness'])
            df.to_csv(file_path, index=False)
            return True
        except Exception as e:
            self.main_window.update_status_message(f"保存数据失败: {str(e)}", "error")
            return False

    def save_current_results_and_exit(self, results):
        """保存当前模拟结果并退出"""
        QMessageBox.information(self.main_window, "流程完成",
            f"已保存当前模拟结果。\n\n"
            f"所有生成的文件已保存在输出目录中。")
    def set_true_original_file(self, original_file):
        """强制设置真正的原始文件路径"""
        self.true_original_file = original_file


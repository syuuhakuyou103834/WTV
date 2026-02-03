import os
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QScrollArea, QGridLayout, QCheckBox, QSizePolicy, QMessageBox,
    QLineEdit, QFileDialog, QMenu, QInputDialog
)
from PyQt5.QtCore import Qt, QSize
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar
)
import pandas as pd
from matplotlib.patches import Circle
from scipy.interpolate import griddata
import matplotlib as mpl
from core.data_processing import load_wafer_data
from core.batch_processing import get_all_csv_files, get_file_priority_info
from ui.batch_point_edit_dialog import BatchPointEditDialog, BatchStatisticsDetailsDialog
import re

class WaferMiniature(FigureCanvas):
    """单个晶圆小图控件"""
    def __init__(self, data, filename, wafer_size=150, width=5, height=5, parent=None):
        self.fig = Figure(figsize=(width, height), dpi=60)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setMinimumSize(80, 80)
        self.data = data
        self.filename = os.path.basename(filename)
        self.wafer_size = wafer_size
        self.unified_norm = None
        
        # 设置紧凑布局
        self.fig.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.95)
        self.draw_wafer()
    
    def set_unified_norm(self, vmin, vmax):
        """设置统一的颜色范围"""
        self.unified_norm = mpl.colors.Normalize(vmin, vmax)
        self.draw_wafer()
    
    def clear_unified_norm(self):
        """清除统一颜色范围"""
        self.unified_norm = None
        self.draw_wafer()
    
    def draw_wafer(self):
        """绘制晶圆缩略图"""
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        
        if self.data is None or len(self.data) == 0:
            ax.text(0.5, 0.5, '数据不足', ha='center', va='center', fontsize=8)
            self.draw()
            return
        
        try:
            # 提取数据
            x, y, z = self.data.T
            wafer_radius = self.wafer_size / 2
            
            # 计算统计信息
            vmin = np.min(z)
            vmax = np.max(z)
            
            # 创建网格
            scale = wafer_radius * 1.05
            x_min, x_max = -scale, scale
            y_min, y_max = -scale, scale
            grid_x, grid_y = np.meshgrid(
                np.linspace(x_min, x_max, 100),
                np.linspace(y_min, y_max, 100)
            )
            
            # 进行插值
            grid_z = griddata((x, y), z, (grid_x, grid_y), method='linear', fill_value=np.nan)
            
            # 添加晶圆轮廓
            distance = np.sqrt(grid_x**2 + grid_y**2)
            grid_z[distance > wafer_radius] = np.nan
            
            # 绘制等高线图
            if self.unified_norm:
                contour = ax.contourf(grid_x, grid_y, grid_z, levels=35,
                                     cmap='jet', norm=self.unified_norm)
            else:
                contour = ax.contourf(grid_x, grid_y, grid_z, levels=35,
                                     cmap='jet', vmin=vmin, vmax=vmax)
            
            # 添加晶圆轮廓
            wafer = Circle((0, 0), wafer_radius, edgecolor='black', fill=False, linewidth=0.8)
            ax.add_patch(wafer)
            
            # 添加颜色条
            cbar = self.fig.colorbar(contour, ax=ax, fraction=0.03, pad=0.01, format="%.1f")
            cbar.set_label('nm', fontsize=6)
            cbar.ax.tick_params(labelsize=6)
            
            # 隐藏坐标轴
            ax.set_axis_off()
            
            # 添加文件名标签
            ax.set_title(self.filename[:25] + ('...' if len(self.filename) > 25 else ''), 
                        fontsize=6, pad=2)
            
            self.draw()
        except Exception as e:
            ax.text(0.5, 0.5, f'绘制错误: {str(e)}', ha='center', va='center', fontsize=7)
            self.draw()

class BatchWaferUI(QWidget):
    """批量晶圆处理界面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.files_data = []  # 存储所有文件数据 (data, filename, file_path)
        self.current_page = 0
        self.per_page = 25  # 每页显示25个晶圆
        self.wafer_size = 150  # 默认尺寸
        self.unified_scale = False
        self.unified_vmin = None
        self.unified_vmax = None
        self.miniatures = []  # 存储所有缩略图对象
        self.pending_update = None  # 等待应用的更新
        self.pending_update_path = None  # 等待更新的文件路径
        
        # UI初始化
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 控制栏
        control_layout = QHBoxLayout()
        
        # 选择文件夹按钮
        self.select_folder_btn = QPushButton("选择文件夹")
        self.select_folder_btn.setFixedWidth(120)
        self.select_folder_btn.clicked.connect(self.select_folder)
        control_layout.addWidget(self.select_folder_btn)
        # 文件夹选择
        self.folder_label = QLabel("选择的数据文件夹: 未选择")
        control_layout.addWidget(self.folder_label)

        # 添加弹性空间分隔左右两部分
        control_layout.addStretch(1)
        
        # 晶圆尺寸标签和选择器
        self.size_label = QLabel("晶圆尺寸 (mm):")
        control_layout.addWidget(self.size_label)
        
        self.size_combo = QComboBox()
        self.size_combo.addItems(["100", "150", "200", "300"])
        self.size_combo.setCurrentIndex(1)  # 默认选择150mm
        self.size_combo.setFixedWidth(80)
        self.size_combo.currentTextChanged.connect(self.set_wafer_size)
        control_layout.addWidget(self.size_combo)
        
        # 统一颜色范围选项
        self.unified_scale_cb = QCheckBox("统一颜色范围")
        self.unified_scale_cb.stateChanged.connect(self.toggle_unified_scale)
        control_layout.addWidget(self.unified_scale_cb)
        
        # 颜色范围设置
        self.vmin_label = QLabel("最小值:")
        control_layout.addWidget(self.vmin_label)
        self.vmin_edit = QLineEdit("")
        self.vmin_edit.setFixedWidth(150)
        control_layout.addWidget(self.vmin_edit)
        
        self.vmax_label = QLabel("最大值:")
        control_layout.addWidget(self.vmax_label)
        self.vmax_edit = QLineEdit("")
        self.vmax_edit.setFixedWidth(150)
        control_layout.addWidget(self.vmax_edit)
        
        self.apply_scale_btn = QPushButton("应用")
        self.apply_scale_btn.setFixedWidth(60)
        self.apply_scale_btn.clicked.connect(self.apply_unified_scale)
        control_layout.addWidget(self.apply_scale_btn)
        
        # 批量编辑按钮
        self.batch_edit_btn = QPushButton("批量数据点编辑")
        self.batch_edit_btn.setFixedWidth(160)
        self.batch_edit_btn.clicked.connect(self.show_batch_point_edit)
        control_layout.addWidget(self.batch_edit_btn)
        
        main_layout.addLayout(control_layout)
        
        # 分隔线
        main_layout.addWidget(QLabel("<hr>"))
        
        # 翻页导航
        nav_layout = QHBoxLayout()
        self.prev_page_btn = QPushButton("上一页")
        self.prev_page_btn.setFixedWidth(80)
        self.prev_page_btn.clicked.connect(self.prev_page)
        nav_layout.addWidget(self.prev_page_btn)
        
        self.page_label = QLabel("页码: 0/0")
        nav_layout.addWidget(self.page_label)
        
        self.next_page_btn = QPushButton("下一页")
        self.next_page_btn.setFixedWidth(80)
        self.next_page_btn.clicked.connect(self.next_page)
        nav_layout.addWidget(self.next_page_btn)
        
        main_layout.addLayout(nav_layout)
        
        # 滚动区域 - 显示晶圆小图
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setHorizontalSpacing(5)
        self.grid_layout.setVerticalSpacing(5)
        
        scroll_area.setWidget(self.grid_widget)
        main_layout.addWidget(scroll_area)
        
        # 禁用统一颜色控件直到有数据
        self.toggle_unified_controls(False)
    
    def set_wafer_size(self, size_str):
        """设置晶圆尺寸"""
        try:
            self.wafer_size = int(size_str)
            # 如果已经有数据显示，刷新显示
            if self.miniatures:
                self.update_display()
        except ValueError:
            self.wafer_size = 150  # 默认值
    
    def toggle_unified_controls(self, enabled):
        """切换统一颜色范围控件状态"""
        self.vmin_label.setEnabled(enabled)
        self.vmin_edit.setEnabled(enabled)
        self.vmax_label.setEnabled(enabled)
        self.vmax_edit.setEnabled(enabled)
        self.apply_scale_btn.setEnabled(enabled)
        self.unified_scale_cb.setEnabled(enabled)
    
    def select_folder(self):
        """选择包含CSV文件的文件夹"""
        folder = QFileDialog.getExistingDirectory(
            self, "选择数据文件夹", "", QFileDialog.ShowDirsOnly
        )
        
        if not folder:
            return
            
        self.folder_label.setText(f"选择的数据文件夹: {folder}")
        
        # 加载所有CSV文件
        self.load_folder_data(folder)

        # 计算全局颜色范围
        self.calculate_global_scale()

        # 启用统一颜色范围控件
        self.toggle_unified_controls(True)

        # 设置首次加载标记，用于触发异常值检测
        self._first_load = True

        # 显示第一页
        self.update_display()
    
    def load_folder_data(self, folder):
        """加载文件夹中的所有CSV文件，自动选择最新版本的优先级文件"""
        self.files_data = []

        # 获取文件优先级信息
        priority_info = get_file_priority_info(folder)
        selected_files = priority_info['selected_files']
        version_details = priority_info['version_details']

        total = len(selected_files)

        # 检查是否存在已处理的文件
        has_error_deleted_files = any(
            '_error_deleted' in os.path.basename(path)
            for path in selected_files
        )

        # 如果有文件版本选择，显示通知
        if any(skipped_files for _, skipped_files, _ in version_details):
            self.show_file_priority_notification(version_details, has_error_deleted_files)

        # 显示加载进度
        self.main_window.update_status_message(f"正在加载文件夹数据, 共 {total} 个文件...")

        # 逐文件加载
        for i, file_path in enumerate(selected_files):
            try:
                data, filename = load_wafer_data(file_path)
                self.files_data.append((data, filename, file_path))
                self.main_window.update_status_message(
                    f"加载进度: {i+1}/{total} - {filename}"
                )
            except Exception as e:
                self.main_window.update_status_message(
                    f"跳过文件 {os.path.basename(file_path)}: 错误 {str(e)}", "error"
                )
                continue

        self.main_window.update_status_message(
            f"成功加载 {len(self.files_data)}/{total} 个晶圆数据文件"
        )

        # 存储是否存在已处理文件的信息
        self.has_processed_files = has_error_deleted_files

    def show_file_priority_notification(self, version_details, has_error_deleted_files=False):
        """显示文件优先级选择通知"""
        if not version_details:
            return

        # 筛选有版本冲突的文件组
        conflict_groups = [(base, skipped, selected)
                          for base, skipped, selected in version_details
                          if skipped]

        if not conflict_groups:
            return

        # 创建通知消息
        msg = f"检测到 {len(conflict_groups)} 个晶圆文件存在多个版本：\n\n"

        # 显示前5个版本组作为示例
        for i, (base_name, skipped_files, selected_file) in enumerate(conflict_groups[:5]):
            msg += f"【{base_name}】:\n"
            for skipped in skipped_files:
                msg += f"  跳过: {skipped}\n"
            msg += f"  选择: {selected_file}\n\n"

        if len(conflict_groups) > 5:
            msg += f"... 还有 {len(conflict_groups) - 5} 个文件组\n\n"

        msg += "系统将优先选择剔除轮数最多的最新版本文件，"
        msg += "以确保使用最高质量的数据进行分析。"

        # 如果存在已处理的文件，添加异常值检测提示
        if has_error_deleted_files:
            msg += "\n\n检测到文件已进行过异常值剔除，故不再进行异常值剔除，"
            msg += "如果需要继续剔除异常值，请在数据(D)菜单栏中点击【异常值再次剔除】。"

        # 显示通知对话框
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("文件版本优先级选择")
        msg_box.setText("自动选择最新版本的文件")
        msg_box.setInformativeText(msg)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    def get_file_summary_info(self):
        """获取当前加载文件的摘要信息，用于调试和用户反馈"""
        if not self.files_data:
            return "未加载任何文件"

        total_files = len(self.files_data)

        # 统计不同类型的文件
        original_files = 0
        first_round_files = 0
        multi_round_files = 0

        for _, filename, _ in self.files_data:
            if '_error_deleted' not in filename:
                original_files += 1
            elif filename.endswith('_error_deleted.csv'):
                first_round_files += 1
            elif '_error_deleted_round' in filename:
                multi_round_files += 1

        processed_files = first_round_files + multi_round_files

        summary = f"文件加载摘要:\n"
        summary += f"• 总文件数: {total_files}\n"
        summary += f"• 原始文件: {original_files}\n"
        summary += f"• 首次异常值处理文件: {first_round_files}\n"
        summary += f"• 多轮异常值处理文件: {multi_round_files}\n"

        if processed_files > 0:
            summary += f"\n注意: 系统已自动选择各文件组的最新版本，"
            summary += f"确保使用最高质量的数据进行分析。"

        return summary
    
    def calculate_global_scale(self):
        """计算所有晶圆的全局厚度范围"""
        all_thickness = []
        for data, _, _ in self.files_data:
            if data is not None and len(data) >= 3:
                all_thickness.append(data[:, 2])

        if all_thickness:
            all_thickness = np.concatenate(all_thickness)
            self.global_min = np.min(all_thickness)
            self.global_max = np.max(all_thickness)
            self.global_mean = np.mean(all_thickness)

            # 设置初始统一范围为 ±10% 的平均值
            self.unified_vmin = self.global_mean * 0.9
            self.unified_vmax = self.global_mean * 1.1

            self.vmin_edit.setText(f"{self.global_min:.1f}")
            self.vmax_edit.setText(f"{self.global_max:.1f}")

    def detect_outliers(self):
        """检测所有晶圆数据中的异常值"""
        outliers_info = {}  # {filename: {outlier_indices: [], outlier_count: int}}

        for data, filename, file_path in self.files_data:
            if data is None or len(data) < 3:
                continue

            # 提取厚度数据
            thickness_values = data[:, 2]

            # 计算四分位数和四分位距
            q1 = np.percentile(thickness_values, 25)
            q3 = np.percentile(thickness_values, 75)
            iqr = q3 - q1

            # 计算异常值边界
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            # 找出异常值的索引
            outlier_mask = (thickness_values < lower_bound) | (thickness_values > upper_bound)
            outlier_indices = np.where(outlier_mask)[0]
            outlier_count = len(outlier_indices)

            # 如果有异常值，记录信息
            if outlier_count > 0:
                file_stem = os.path.splitext(filename)[0]
                outliers_info[file_stem] = {
                    'outlier_indices': outlier_indices,
                    'outlier_count': outlier_count,
                    'lower_bound': lower_bound,
                    'upper_bound': upper_bound,
                    'data': data,
                    'file_path': file_path,
                    'filename': filename
                }

        return outliers_info

    def show_outlier_dialog(self, outliers_info, is_manual_trigger=False):
        """显示异常值检测和处理对话框"""
        if not outliers_info:
            return

        # 获取存在异常值的晶圆名称列表
        outlier_wafers = list(outliers_info.keys())

        # 创建确认对话框
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question)

        # 根据触发方式设置不同的标题和文本
        if is_manual_trigger:
            msg_box.setWindowTitle("异常值再次剔除")
            msg_box.setText("再次检测到异常值")
        else:
            msg_box.setWindowTitle("异常值检测")
            msg_box.setText("检测到异常值")

        # 构建详细信息文本
        details = f"在以下 {len(outlier_wafers)} 片晶圆中检测到超过四分位数1.5倍四分位距的异常值：\n\n"
        for wafer_name in outlier_wafers:
            info = outliers_info[wafer_name]
            details += f"• {wafer_name}: {info['outlier_count']} 个异常点\n"

        details += "\n是否需要程序自动剔除这些异常值？"
        msg_box.setInformativeText(details)

        # 添加按钮
        yes_button = msg_box.addButton("是", QMessageBox.YesRole)
        no_button = msg_box.addButton("否", QMessageBox.NoRole)
        msg_box.setDefaultButton(no_button)

        # 显示对话框并获取用户选择
        msg_box.exec_()

        if msg_box.clickedButton() == yes_button:
            # 用户选择剔除异常值
            self.remove_outliers(outliers_info, is_manual_trigger)

    def remove_outliers(self, outliers_info, is_manual_trigger=False):
        """剔除异常值并保存为新文件"""
        processed_files = []

        for wafer_name, info in outliers_info.items():
            try:
                # 获取原始数据
                original_data = info['data']
                outlier_indices = info['outlier_indices']

                # 创建掩码，保留非异常值
                mask = np.ones(len(original_data), dtype=bool)
                mask[outlier_indices] = False

                # 剔除异常值
                cleaned_data = original_data[mask]

                # 构建新文件名
                file_path = info['file_path']
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                directory = os.path.dirname(file_path)

                # 根据原始文件名和触发方式生成新文件名
                if base_name.endswith('_error_deleted'):
                    # 已经是处理过的文件，再次处理添加序号
                    new_base_name = base_name + f"_round2"
                    new_filename = f"{new_base_name}.csv"
                else:
                    # 原始文件，正常处理
                    new_filename = f"{base_name}_error_deleted.csv"

                new_file_path = os.path.join(directory, new_filename)

                # 保存处理后的数据
                if self.save_modified_data(cleaned_data, new_file_path):
                    processed_files.append((base_name, new_filename))
                    # 更新状态消息
                    if hasattr(self, 'main_window') and self.main_window:
                        self.main_window.update_status_message(
                            f"已处理 {base_name} 的异常值，保存为 {new_filename}"
                        )

            except Exception as e:
                if hasattr(self, 'main_window') and self.main_window:
                    self.main_window.update_status_message(
                        f"处理 {wafer_name} 时出错: {str(e)}", "error"
                    )

        # 显示处理结果
        if processed_files:
            if is_manual_trigger:
                title = "异常值再次剔除完成"
                msg_type = "再次"
            else:
                title = "异常值处理完成"
                msg_type = ""

            result_msg = f"已成功处理以下 {len(processed_files)} 片晶圆的异常值，并保存为新文件：\n\n"
            for original_name, new_name in processed_files:
                result_msg += f"• {new_name}\n"
            result_msg += f"\n异常值已按照箱型图统计定义（超过四分位数1.5倍四分位距）{msg_type}剔除。"

            QMessageBox.information(self, title, result_msg)
        else:
            QMessageBox.warning(self, "处理失败", "没有成功处理任何文件")

    def _detect_and_show_outliers(self, first_load_flag=None):
        """异步检测并显示异常值对话框"""
        try:
            # 检测异常值
            outliers_info = self.detect_outliers()

            # 如果有异常值，显示处理对话框
            if outliers_info:
                self.show_outlier_dialog(outliers_info, is_manual_trigger=False)
            else:
                QMessageBox.information(self, "异常值检测", "未检测到需要处理的异常值。")

        except Exception as e:
            if hasattr(self, 'main_window') and self.main_window:
                self.main_window.update_status_message(
                    f"异常值检测时出错: {str(e)}", "error"
                )

    def trigger_outlier_detection(self):
        """手动触发异常值检测（供菜单栏调用）"""
        if not self.files_data or len(self.files_data) == 0:
            QMessageBox.warning(self, "无数据", "请先加载批量数据")
            return

        try:
            # 检测异常值
            outliers_info = self.detect_outliers()

            # 如果有异常值，显示处理对话框
            if outliers_info:
                self.show_outlier_dialog(outliers_info, is_manual_trigger=True)
            else:
                QMessageBox.information(self, "异常值再次剔除", "未检测到需要处理的异常值。")

        except Exception as e:
            QMessageBox.critical(self, "检测错误", f"异常值检测时出错: {str(e)}")
    
    def toggle_unified_scale(self, state):
        """切换统一颜色范围模式"""
        self.unified_scale = (state == Qt.Checked)
        
        # 应用统一颜色范围
        if self.unified_scale and self.unified_vmin is not None and self.unified_vmax is not None:
            for miniature in self.miniatures:
                miniature.set_unified_norm(self.unified_vmin, self.unified_vmax)
        else:
            for miniature in self.miniatures:
                miniature.clear_unified_norm()
    
    def apply_unified_scale(self):
        """应用手动输入的统一颜色范围"""
        try:
            self.unified_vmin = float(self.vmin_edit.text())
            self.unified_vmax = float(self.vmax_edit.text())
            
            if self.unified_vmin >= self.unified_vmax:
                raise ValueError("最小值必须小于最大值")
                
            # 如果当前启用了统一颜色模式，立即更新
            if self.unified_scale:
                for miniature in self.miniatures:
                    miniature.set_unified_norm(self.unified_vmin, self.unified_vmax)
                    
        except Exception as e:
            QMessageBox.warning(self, "输入错误", str(e))
    
    def update_display(self):
        """更新当前页面的显示"""
        # 清除当前网格内容
        self.clear_grid()
        
        # 计算总页数
        total_count = len(self.files_data)
        page_count = max(1, (total_count - 1) // self.per_page + 1)
        self.page_label.setText(f"页码: {self.current_page+1}/{page_count}")
        
        # 计算当前页的起始和结束索引
        start_idx = self.current_page * self.per_page
        end_idx = min((self.current_page + 1) * self.per_page, total_count)
        
        # 没有文件时显示提示
        if total_count == 0:
            no_data_label = QLabel("请选择包含CSV文件的文件夹")
            no_data_label.setAlignment(Qt.AlignCenter)
            self.grid_layout.addWidget(no_data_label, 0, 0, 5, 5)
            return
        
        # 显示当前页的晶圆小图 (5x5网格)
        self.miniatures = []
        for idx in range(start_idx, end_idx):
            data, filename, file_path = self.files_data[idx]
            
            # 网格位置
            row = (idx - start_idx) // 5  # 每行5个晶圆
            col = (idx - start_idx) % 5
            
            # 创建小图控件
            miniature = WaferMiniature(
                data, 
                filename, 
                wafer_size=self.wafer_size,
                parent=self.grid_widget
            )
            
            # 设置上下文菜单支持
            miniature.setContextMenuPolicy(Qt.CustomContextMenu)
            miniature.customContextMenuRequested.connect(
                lambda pos, fpath=file_path, data=data: self.show_context_menu(pos, fpath)
            )
            
            # 双击事件
            miniature.mpl_connect('button_press_event', 
                                 lambda event, fpath=file_path: self.on_miniature_click(event, fpath))
            
            # 绘制前设置统一颜色范围
            if self.unified_scale and self.unified_vmin is not None and self.unified_vmax is not None:
                miniature.set_unified_norm(self.unified_vmin, self.unified_vmax)
            
            self.grid_layout.addWidget(miniature, row, col)
            self.miniatures.append(miniature)
        
        # 刷新显示
        self.update()
        self.grid_widget.update()

        # 在可视化完成后检测异常值（只在首次加载时检测，且不存在已处理文件时）
        if self.current_page == 0 and hasattr(self, '_first_load'):
            # 立即清除首次加载标记，避免重复触发
            first_load_flag = self._first_load
            delattr(self, '_first_load')

            # 如果存在已处理的文件，不进行自动异常值检测
            if hasattr(self, 'has_processed_files') and self.has_processed_files:
                return

            # 异步检测异常值，避免阻塞UI
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, lambda: self._detect_and_show_outliers(first_load_flag))
    
    def clear_grid(self):
        """清除5x5网格中的内容"""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
    
    def prev_page(self):
        """跳转到上一页"""
        total_count = len(self.files_data)
        page_count = max(1, (total_count - 1) // self.per_page + 1)
        
        if self.current_page > 0:
            self.current_page -= 1
            self.update_display()
    
    def next_page(self):
        """跳转到下一页"""
        total_count = len(self.files_data)
        page_count = max(1, (total_count - 1) // self.per_page + 1)
        
        if self.current_page < page_count - 1:
            self.current_page += 1
            self.update_display()
    
    def on_miniature_click(self, event, file_path):
        """处理晶圆缩略图点击事件"""
        if event.dblclick:  # 双击
            # 发送文件路径到单片处理窗口
            if self.main_window and hasattr(self.main_window, 'single_wafer_tab'):
                self.main_window.single_wafer_tab.load_file_directly(file_path, self.wafer_size)
                self.main_window.tab_widget.setCurrentIndex(0)  # 切换到单片视图
    
    def show_context_menu(self, global_pos, file_path):
        """显示上下文菜单：更新回批量视图"""
        # 如果此文件有等待应用的更新
        if self.pending_update is not None and self.pending_update_path == file_path:
            menu = QMenu(self)
            apply_action = menu.addAction("应用更新到批量视图")
            
            # 显示菜单并获取用户选择
            action = menu.exec_(global_pos)
            
            if action == apply_action:
                self.update_file_data(file_path, self.pending_update)
                
                # 清除等待状态
                self.pending_update = None
                self.pending_update_path = None
                
                # 刷新显示
                self.update_display()
    
    def prepare_for_update(self, file_path, data):
        """准备更新指定文件路径的数据（由单片视图调用）"""
        # 验证数据格式
        if (file_path is None or 
            data is None or 
            not isinstance(data, np.ndarray) or 
            data.shape[1] != 3):
            print(f"Ignoring invalid update data for {file_path}")
            return
        
        self.pending_update = data
        self.pending_update_path = file_path
    
    def update_file_data(self, file_path, new_data):
        """更新指定文件的数据"""
        updated = False
        
        for i, (_, _, fpath) in enumerate(self.files_data):
            if fpath == file_path:
                # 更新文件名（保留原始文件名）
                filename = self.files_data[i][1]
                self.files_data[i] = (new_data, filename, file_path)
                updated = True
                break
        
        if updated:
            # 显示更新通知
            msg = f"已更新 {os.path.basename(file_path)} 的数据"
            if hasattr(self, 'main_window') and self.main_window:
                self.main_window.update_status_message(msg)
            else:
                print(msg)  # 回退打印到控制台
            
            # 刷新显示（如果需要）
            if self.miniatures:
                self.update_display()
        else:
            # 如果未找到文件，显示警告
            QMessageBox.warning(self, "更新失败", "未找到匹配的文件路径")
            if hasattr(self, 'main_window') and self.main_window:
                self.main_window.update_status_message("更新失败：未找到匹配的文件路径", "error")
   
    
    def get_files_data(self):
        """返回所有文件数据"""
        return self.files_data
    
    # 核心方法 - 添加必要的参数
    def process_batch_files(self, stats_data, operation, operation_type, 
                            method, start_point_type, operation_param, range_value):
        """
        根据统计信息批量处理文件夹中的所有文件中的数据点,
        仅当文件中有实际修改时才生成新文件
        """
        modified_files = []
        
        if not self.files_data:
            return modified_files
            
        # 获取父窗口用于状态更新
        main_window = getattr(self, 'main_window', None)
        total_files = len(self.files_data)
        processed_count = 0
        
        for idx, (data, filename, file_path) in enumerate(self.files_data):
            # 如果没有该文件的统计信息，跳过
            file_stem = os.path.splitext(filename)[0]
            if file_stem not in stats_data:
                continue
                
            stats = stats_data[file_stem]
            
            # 提取厚度数据
            z = data[:, 2]
            
            # 根据方法类型计算边界
            if method == "relative":
                # 相对范围模式
                if start_point_type == "max":
                    min_bound = stats['start_value'] - range_value
                    max_bound = stats['start_value']
                else:  # min
                    min_bound = stats['start_value']
                    max_bound = stats['start_value'] + range_value
            else:
                # 绝对范围模式
                if isinstance(range_value, tuple) and len(range_value) == 2:
                    min_bound, max_bound = range_value
                else:
                    # 无效范围，跳过此文件
                    continue
            
            # 创建数据掩码
            mask = (z >= min_bound) & (z <= max_bound)
            
            # 根据操作类型处理数据
            if operation == 'modify' and operation_param is not None:
                # 检查是否实际有变化
                if np.any(data[mask, 2] != operation_param):
                    modified_data = data.copy()
                    modified_data[mask, 2] = operation_param
                    do_processing = True  # 标记为需要处理
                else:
                    do_processing = False  # 没有实际变化
            elif operation == 'delete':
                if operation_type == "in_range":
                    # 如果范围外所有点都已存在, 表示无变化
                    if np.any(mask):
                        modified_data = data[~mask]  # 保留范围外的点
                        do_processing = True
                    else:
                        do_processing = False
                else:  # out_of_range
                    # 如果范围内所有点都未删除, 表示无变化
                    if np.any(~mask):
                        modified_data = data[mask]   # 保留范围内的点
                        do_processing = True
                    else:
                        do_processing = False
            else:
                # 无效操作，跳过
                continue
            
            # 只有当文件中有实际修改时才保存
            if do_processing:
                # 保存修改后的文件
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                save_path = os.path.join(
                    os.path.dirname(file_path),
                    f"{base_name}_modified.csv"  # 添加modified后缀
                )
                
                # 保存文件
                if self.save_modified_data(modified_data, save_path):
                    modified_files.append(save_path)
                    processed_count += 1
                    
                    # 更新状态
                    if main_window:
                        main_window.update_status_message(
                            f"已修改并保存: {base_name}"
                        )
            
        return modified_files   
    
    def save_modified_data(self, data, file_path):
        """保存修改后的数据到文件"""
        try:
            df = pd.DataFrame(data, columns=['x', 'y', 'thickness'])
            df.to_csv(file_path, index=False)
            return True
        except Exception as e:
            if hasattr(self, 'main_window') and self.main_window:
                self.main_window.update_status_message(f"保存失败: {str(e)}", "error")
            return False
    
    def show_batch_point_edit(self):
        """显示批量数据点处理对话框"""
        if not self.files_data or len(self.files_data) == 0:
            QMessageBox.warning(self, "无数据", "请先加载批量数据")
            return
            
        # 创建并显示对话框
        dialog = BatchPointEditDialog(self)
        dialog.exec_()
        
        # 如果有文件被修改，更新显示
        if dialog.modified_files and hasattr(self, 'update_display'):
            self.update_display()

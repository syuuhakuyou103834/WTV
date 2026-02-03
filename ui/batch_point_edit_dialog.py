#batch_point_edit_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QCheckBox, QPushButton, QMessageBox,
    QButtonGroup, QGroupBox, QRadioButton, QSizePolicy,
    QComboBox, QTableWidget, QTableWidgetItem, QScrollArea,
    QAbstractItemView, QWidget, QSplitter, QGridLayout,
    QStackedWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator, QDoubleValidator
import re
import os
import numpy as np
import pandas as pd

class BatchStatisticsDetailsDialog(QDialog):
    """显示详细结果的对话框"""
    def __init__(self, stats_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("晶圆处理详细统计信息")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # 创建表格
        self.details_table = QTableWidget()
        # 增加一列显示保留目标数量
        self.details_table.setColumnCount(10)  # 10列
        self.details_table.setHorizontalHeaderLabels([
            "晶圆文件", "最大值", "最小值", "第25%位", "中位数", "第75%位",
            "起点值", "保留点数", "删除点数", "保留目标"
        ])
        self.details_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.details_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.details_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.details_table.setSortingEnabled(True)
        
        # 设置表格数据
        self.set_table_data(stats_data)
        
        # 添加表格到滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.details_table)
        layout.addWidget(scroll_area)
        
    def set_table_data(self, stats_data):
        """填充表格数据"""
        self.details_table.setRowCount(len(stats_data))
        self.details_table.setSortingEnabled(False)  # 排序时禁用更新
        
        # 清除现有数据
        self.details_table.clearContents()
        
        # 填充表格
        for row, (filename, stats) in enumerate(stats_data.items()):
            # 文件名
            self.details_table.setItem(row, 0, QTableWidgetItem(filename))
            
            # 统计值
            self.details_table.setItem(row, 1, QTableWidgetItem(f"{stats['max']:.4f}"))
            self.details_table.setItem(row, 2, QTableWidgetItem(f"{stats['min']:.4f}"))
            self.details_table.setItem(row, 3, QTableWidgetItem(f"{stats['q25']:.4f}"))
            self.details_table.setItem(row, 4, QTableWidgetItem(f"{stats['median']:.4f}"))
            self.details_table.setItem(row, 5, QTableWidgetItem(f"{stats['q75']:.4f}"))
            
            # 起点值
            self.details_table.setItem(row, 6, QTableWidgetItem(f"{stats['start_value']:.4f}"))
            
            # 保留和删除点数
            self.details_table.setItem(row, 7, QTableWidgetItem(str(stats['keep_count'])))
            self.details_table.setItem(row, 8, QTableWidgetItem(str(stats['delete_count'])))
            
            # 保留目标数量
            self.details_table.setItem(row, 9, QTableWidgetItem(str(stats['target_count'])))
        
        # 调整列宽和行高
        self.details_table.resizeColumnsToContents()
        self.details_table.resizeRowsToContents()
        
        # 重新启用排序
        self.details_table.setSortingEnabled(True)


class BatchPointEditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量数据点处理")
        self.setMinimumSize(1100, 650)  # 增加窗口尺寸以适应新布局
        
        # 存储统计信息的字典 {文件名: {max: , min: , q1: , median: , q3: , keep_count: , delete_count: }}
        self.stats_data = {}
        self.modified_files = []  # 存储修改后的文件信息
        self.result_data = None  # 存储结果数据
        self.current_start_point = "max"  # 默认从最大值开始
        self.selected_method = "relative"  # 默认选择相对范围
        
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # 左侧控制面板
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(10)
        
        # === 功能选择区域 ===
        method_group = QGroupBox("功能选择 (必须二选一)")
        method_layout = QHBoxLayout(method_group)
        
        # 使用单选按钮组确保互斥
        self.method_group = QButtonGroup()
        
        # 相对范围筛选单选按钮
        self.rel_method_rb = QRadioButton("根据相对范围筛选")
        self.rel_method_rb.setChecked(True)  # 默认选择相对范围
        self.method_group.addButton(self.rel_method_rb, 0)
        method_layout.addWidget(self.rel_method_rb)
        
        # 绝对范围筛选单选按钮
        self.abs_method_rb = QRadioButton("根据绝对范围筛选")
        self.abs_method_rb.setChecked(False)
        self.method_group.addButton(self.abs_method_rb, 1)
        method_layout.addWidget(self.abs_method_rb)
        
        method_layout.addStretch(1)
        left_layout.addWidget(method_group)
        
        # === 功能设置堆叠区域 ===
        self.method_stack = QStackedWidget()
        
        # === 相对范围设置卡片 ===
        rel_method_widget = QWidget()
        rel_method_layout = QVBoxLayout(rel_method_widget)
        
        rel_range_group = QGroupBox("相对范围设置")
        rel_range_layout = QGridLayout(rel_range_group)
        rel_range_layout.setColumnStretch(0, 1)
        rel_range_layout.setColumnStretch(1, 2)
        rel_range_layout.setColumnStretch(2, 1)
        rel_range_layout.setColumnStretch(3, 2)
        
        # 第1行：从最大值开始 (使用单选按钮)
        self.max_method_rb = QRadioButton("从最大值开始")
        self.max_method_rb.setChecked(True)  # 默认选最大值
        self.max_method_rb.toggled.connect(lambda: self.toggle_start_point("max"))
        rel_range_layout.addWidget(self.max_method_rb, 0, 0)
        
        self.max_options = QComboBox()
        self.max_options.addItems(["最大值", "第25%位", "中位数", "第75%位"])
        self.max_options.setCurrentIndex(0)  # 默认选择最大值
        rel_range_layout.addWidget(self.max_options, 0, 1)
        
        rel_range_layout.addWidget(QLabel("范围:"), 0, 2)
        self.range_value_edit_max = QLineEdit("100.0")
        self.range_value_edit_max.setValidator(QDoubleValidator(0.0, 10000.0, 6))
        rel_range_layout.addWidget(self.range_value_edit_max, 0, 3)
        
        # 第2行：从最小值开始 (使用单选按钮)
        self.min_method_rb = QRadioButton("从最小值开始")
        self.min_method_rb.setChecked(False)
        self.min_method_rb.toggled.connect(lambda: self.toggle_start_point("min"))
        rel_range_layout.addWidget(self.min_method_rb, 1, 0)
        
        self.min_options = QComboBox()
        self.min_options.addItems(["最小值", "第25%位", "中位数", "第75%位"])
        self.min_options.setCurrentIndex(0)  # 默认选择最小值
        self.min_options.setEnabled(False)  # 初始禁用最小值选项
        rel_range_layout.addWidget(self.min_options, 1, 1)
        
        rel_range_layout.addWidget(QLabel("范围:"), 1, 2)
        self.range_value_edit_min = QLineEdit("100.0")
        self.range_value_edit_min.setValidator(QDoubleValidator(0.0, 10000.0, 6))
        self.range_value_edit_min.setEnabled(False)
        rel_range_layout.addWidget(self.range_value_edit_min, 1, 3)
        
        rel_method_layout.addWidget(rel_range_group)
        
        # 说明标签
        rel_info = QLabel(
            "此功能用于筛选起始点附近范围内的数据点:\n"
            "• [最大值模式]: 保留从起始点 - 范围值 到 起始点之间的点\n"
            "• [最小值模式]: 保留从起始点 到 起始点 + 范围值之间的点"
        )
        rel_info.setWordWrap(True)
        rel_method_layout.addWidget(rel_info)
        
        rel_method_layout.addStretch(1)
        self.method_stack.addWidget(rel_method_widget)
        
        # === 绝对范围设置卡片 ===
        abs_method_widget = QWidget()
        abs_method_layout = QVBoxLayout(abs_method_widget)
        
        abs_range_group = QGroupBox("绝对范围设置")
        abs_range_layout = QVBoxLayout(abs_range_group)
        
        abs_range_layout.addWidget(QLabel("请输入绝对厚度范围："))
        self.range_label = QLabel("支持格式: 0,1800 或 (0,1800) 或 0 1800 或 0-1800")
        self.range_label.setWordWrap(True)  # 允许多行显示
        abs_range_layout.addWidget(self.range_label)
        
        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText("输入厚度范围（例如: 0,1800）")
        self.range_edit.textChanged.connect(self.update_range_status)
        abs_range_layout.addWidget(self.range_edit)
        
        # 状态标签
        self.status_label = QLabel("等待输入...")
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        abs_range_layout.addWidget(self.status_label)
        
        abs_method_layout.addWidget(abs_range_group)
        
        # 说明标签
        abs_info = QLabel(
            "此功能用于筛选指定绝对厚度范围内的数据点:\n"
            "只处理厚度在此范围内的数据点，与其他数值无关"
        )
        abs_info.setWordWrap(True)
        abs_method_layout.addWidget(abs_info)
        
        abs_method_layout.addStretch(1)
        self.method_stack.addWidget(abs_method_widget)
        
        # 添加堆栈到左侧布局
        left_layout.addWidget(self.method_stack)
        
        # === 操作选择区域 ===
        action_group = QGroupBox("操作选项")
        action_layout = QVBoxLayout(action_group)
        
        # 操作单选按钮组
        action_button_group = QButtonGroup(action_group)
        
        # 选项1：删除范围内的点
        self.delete_in_radio = QRadioButton("删除范围内的数据点")
        self.delete_in_radio.setChecked(True)  # 默认为删除范围内的点
        action_button_group.addButton(self.delete_in_radio)
        action_layout.addWidget(self.delete_in_radio)
        
        # 选项2：仅保留范围内的点（删除范围外的点）
        self.keep_in_radio = QRadioButton("仅保留范围内的数据点（删除范围外）")
        action_button_group.addButton(self.keep_in_radio)
        action_layout.addWidget(self.keep_in_radio)
        
        # 选项3：修改范围内的点为固定值
        self.modify_radio = QRadioButton("修改范围内的数据点为固定值")
        action_button_group.addButton(self.modify_radio)
        action_layout.addWidget(self.modify_radio)
        
        # 新值设置
        self.new_value_layout = QHBoxLayout()
        self.new_value_label = QLabel("新厚度值 (nm)：")
        self.new_value_label.setEnabled(False)
        self.new_value_edit = QLineEdit()
        self.new_value_edit.setDisabled(True)  # 初始禁用
        self.new_value_edit.setPlaceholderText("输入替换的厚度值")
        
        self.new_value_layout.addWidget(self.new_value_label)
        self.new_value_layout.addWidget(self.new_value_edit)
        action_layout.addLayout(self.new_value_layout)
        
        # 连接信号
        self.modify_radio.toggled.connect(self.new_value_label.setEnabled)
        self.modify_radio.toggled.connect(self.new_value_edit.setEnabled)
        left_layout.addWidget(action_group)
        
        # 操作按钮布局
        button_layout = QHBoxLayout()
        
        self.details_btn = QPushButton("详细信息")
        self.details_btn.setFixedWidth(100)
        self.details_btn.setEnabled(False)
        self.details_btn.clicked.connect(self.show_details)
        button_layout.addWidget(self.details_btn)
        
        self.calculate_btn = QPushButton("预览")
        self.calculate_btn.setFixedWidth(100)
        self.calculate_btn.setToolTip("检查有多少文件将被影响")
        self.calculate_btn.clicked.connect(self.preview_action)
        button_layout.addWidget(self.calculate_btn)
        
        self.apply_btn = QPushButton("应用")
        self.apply_btn.setFixedWidth(100)
        self.apply_btn.clicked.connect(self.process_action)
        button_layout.addWidget(self.apply_btn)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.setFixedWidth(100)
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        button_layout.addStretch(1)
        left_layout.addLayout(button_layout)
        
        # 右侧详情面板
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 创建表格
        right_label = QLabel("<b>统计信息预览 (点击表头可排序)</b>")
        right_layout.addWidget(right_label)
        
        self.details_table = QTableWidget()
        self.details_table.setColumnCount(10)  # 10列
        self.details_table.setHorizontalHeaderLabels([
            "晶圆文件", "最大值", "最小值", "第25%位", "中位数", "第75%位",
            "起点值", "保留点数", "删除点数", "保留目标"
        ])
        self.details_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.details_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.details_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.details_table.setSortingEnabled(True)
        self.details_table.setMinimumHeight(400)
        
        # 添加表格到滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.details_table)
        right_layout.addWidget(scroll_area)
        
        # 添加分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])  # 设置左右比例
        
        # 将分割器添加到主布局
        main_layout.addWidget(splitter, 1)  # 设置拉伸因子为1
        
        # === 连接信号 ===
        self.rel_method_rb.toggled.connect(self.switch_method)
        self.abs_method_rb.toggled.connect(self.switch_method)
        
        # 设置窗口策略
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
    
    def switch_method(self):
        """切换功能方法"""
        if self.rel_method_rb.isChecked():
            self.selected_method = "relative"
            self.method_stack.setCurrentIndex(0)  # 显示相对范围设置
            
            # 重置起点选择并更新UI状态
            self.max_method_rb.setChecked(True)
            self.min_options.setEnabled(False)
            self.range_value_edit_min.setEnabled(False)
        else:
            self.selected_method = "absolute"
            self.method_stack.setCurrentIndex(1)  # 显示绝对范围设置
            
        # 重置详细数据
        self.stats_data = {}
        self.details_table.clearContents()
        self.details_table.setRowCount(0)
        self.details_btn.setEnabled(False)
    
    def toggle_start_point(self, point_type):
        """切换起点类型 (max/min) 并更新UI状态"""
        if point_type == "max" and self.max_method_rb.isChecked():
            self.current_start_point = "max"
            # 激活最大值相关的控件
            self.max_options.setEnabled(True)
            self.range_value_edit_max.setEnabled(True)
            # 禁用最小值相关的控件
            self.min_options.setEnabled(False)
            self.range_value_edit_min.setEnabled(False)
        elif point_type == "min" and self.min_method_rb.isChecked():
            self.current_start_point = "min"
            # 激活最小值相关的控件
            self.min_options.setEnabled(True)
            self.range_value_edit_min.setEnabled(True)
            # 禁用最大值相关的控件
            self.max_options.setEnabled(False)
            self.range_value_edit_max.setEnabled(False)
        
        # 重置细节按钮状态
        self.details_btn.setEnabled(False)
    
    def update_range_status(self):
        """当范围输入变化时更新状态标签"""
        range_str = self.range_edit.text().strip()
        if not range_str:
            self.status_label.setText("等待输入...")
            return
            
        range_values = self.parse_range(range_str)
        if range_values:
            min_val, max_val = range_values
            self.status_label.setText(f"准备处理厚度在 {min_val:.2f}nm 和 {max_val:.2f}nm 之间的点")
        else:
            self.status_label.setText("输入无效，请参考示例格式输入")
    
    def parse_range(self, range_str):
        """解析并验证范围字符串，支持多种格式"""
        # 去除可能存在的括号
        range_str = range_str.strip().replace("(", "").replace(")", "")
        
        # 如果使用逗号分隔
        if "," in range_str:
            parts = range_str.split(",")
        # 如果使用空格分隔
        elif " " in range_str:
            parts = range_str.split()
        # 如果使用短横线分隔
        elif "-" in range_str:
            parts = range_str.split("-")
        # 如果没有明显分隔符
        else:
            # 尝试匹配数字对
            matches = re.findall(r'[\d.]+', range_str)
            if len(matches) >= 2:
                parts = [matches[0], matches[1]]
            else:
                return None
        
        # 验证解析结果
        if len(parts) >= 2:
            try:
                min_val = float(parts[0].strip())
                max_val = float(parts[1].strip())
                
                # 确保最小值小于最大值
                if min_val > max_val:
                    min_val, max_val = max_val, min_val
                    
                return min_val, max_val
                
            except (ValueError, TypeError):
                return None
        else:
            return None

    def preview_action(self):
        """预览操作将影响多少文件"""
        # 获取父窗口引用
        parent = self.parent()
        
        if hasattr(parent, 'get_files_data'):
            files_data = parent.get_files_data()
            if not files_data:
                QMessageBox.warning(self, "无数据", "请先在批量处理页面加载数据")
                return
        else:
            QMessageBox.critical(self, "错误", "无法获取批量数据")
            return
            
        # 收集统计信息
        self.stats_data = {}
        processed_count = 0
        
        # 处理每个文件
        for data, filename, _ in files_data:
            if data is None or len(data) < 3:
                continue
                
            thickness_values = data[:, 2]
            n_points = len(thickness_values)
            
            # 计算统计值
            stats = {
                'max': np.max(thickness_values),
                'min': np.min(thickness_values),
                'q25': np.percentile(thickness_values, 25),
                'median': np.median(thickness_values),
                'q75': np.percentile(thickness_values, 75)
            }
            
            # 根据选择的处理方法处理数据
            if self.selected_method == "relative":
                # ==== 相对范围处理 ====
                if self.current_start_point == "max":
                    # 获取范围值
                    try:
                        range_value = float(self.range_value_edit_max.text())
                        if range_value <= 0:
                            raise ValueError("范围值必须大于0")
                    except Exception as e:
                        QMessageBox.warning(self, "输入错误", str(e))
                        return
                    
                    # 确定起始值
                    option_text = self.max_options.currentText()
                    if option_text == "最大值":
                        start_value = stats['max']
                    elif option_text == "第25%位":
                        start_value = stats['q25']
                    elif option_text == "中位数":
                        start_value = stats['median']
                    elif option_text == "第75%位":
                        start_value = stats['q75']
                    else:
                        start_value = stats['max']
                    
                    # 计算保留范围
                    min_bound = start_value - range_value
                    max_bound = start_value
                    stats['start_value'] = start_value
                
                else:  # min
                    try:
                        range_value = float(self.range_value_edit_min.text())
                        if range_value <= 0:
                            raise ValueError("范围值必须大于0")
                    except Exception as e:
                        QMessageBox.warning(self, "输入错误", str(e))
                        return
                    
                    # 确定起始值
                    option_text = self.min_options.currentText()
                    if option_text == "最小值":
                        start_value = stats['min']
                    elif option_text == "第25%位":
                        start_value = stats['q25']
                    elif option_text == "中位数":
                        start_value = stats['median']
                    elif option_text == "第75%位":
                        start_value = stats['q75']
                    else:
                        start_value = stats['min']
                    
                    # 计算保留范围
                    min_bound = start_value
                    max_bound = start_value + range_value
                    stats['start_value'] = start_value
                
                # 创建基于范围的掩码
                mask = (thickness_values >= min_bound) & (thickness_values <= max_bound)
                stats['target_count'] = np.sum(mask)  # 范围内点数量
            
            else:  # absolute method
                # ==== 绝对范围处理 ====
                range_str = self.range_edit.text().strip()
                if not range_str:
                    QMessageBox.warning(self, "输入错误", "请先输入绝对范围")
                    return
                
                range_values = self.parse_range(range_str)
                if not range_values:
                    QMessageBox.warning(self, "格式错误", "请输入有效的绝对厚度范围")
                    return
                
                min_val, max_val = range_values
                
                # 计算绝对范围内的点
                mask = (thickness_values >= min_val) & (thickness_values <= max_val)
                stats['target_count'] = np.sum(mask)  # 范围内点数量
                stats['start_value'] = min_val  # 记录下界值
            
            # 计算保留和删除的数量 (根据操作类型的预览计算)
            if self.delete_in_radio.isChecked() or self.modify_radio.isChecked():
                # 删除或修改范围内的点 -> 这些点将不再保留在原始位置
                stats['keep_count'] = n_points - stats['target_count']
                stats['delete_count'] = stats['target_count']
            else:  # 仅保留范围内的点 (删除范围外的点)
                stats['keep_count'] = stats['target_count']
                stats['delete_count'] = n_points - stats['keep_count']
            
            # 存储文件名干细胞作为键
            file_stem = os.path.splitext(filename)[0]
            self.stats_data[file_stem] = stats
            processed_count += 1
        
        # 更新状态
        self.details_btn.setEnabled(len(self.stats_data) > 0)
        self.update_details_table()
        
        # 显示结果
        QMessageBox.information(self, "预览完成", 
                               f"已分析 {processed_count} 个晶圆的统计信息\n点击'详细信息'查看详情")
    
    def update_details_table(self):
        """更新详细信息表格"""
        if not self.stats_data:
            return
            
        self.details_table.setRowCount(len(self.stats_data))
        self.details_table.setSortingEnabled(False)  # 排序时禁用更新
        
        # 清除现有数据
        self.details_table.clearContents()
        
        # 填充表格
        for row, (filename, stats) in enumerate(self.stats_data.items()):
            # 文件名
            self.details_table.setItem(row, 0, QTableWidgetItem(filename))
            
            # 统计值
            self.details_table.setItem(row, 1, QTableWidgetItem(f"{stats['max']:.4f}"))
            self.details_table.setItem(row, 2, QTableWidgetItem(f"{stats['min']:.4f}"))
            self.details_table.setItem(row, 3, QTableWidgetItem(f"{stats['q25']:.4f}"))
            self.details_table.setItem(row, 4, QTableWidgetItem(f"{stats['median']:.4f}"))
            self.details_table.setItem(row, 5, QTableWidgetItem(f"{stats['q75']:.4f}"))
            
            # 起点值
            self.details_table.setItem(row, 6, QTableWidgetItem(f"{stats['start_value']:.4f}"))
            
            # 保留和删除点数
            self.details_table.setItem(row, 7, QTableWidgetItem(str(stats['keep_count'])))
            self.details_table.setItem(row, 8, QTableWidgetItem(str(stats['delete_count'])))
            
            # 保留目标数量
            self.details_table.setItem(row, 9, QTableWidgetItem(str(stats['target_count'])))
        
        # 调整列宽和行高
        self.details_table.resizeColumnsToContents()
        self.details_table.resizeRowsToContents()
        
        # 重新启用排序
        self.details_table.setSortingEnabled(True)
    
    def process_action(self):
        """处理应用按钮点击事件"""
        # 执行预览操作以获取最新统计信息
        self.preview_action()
        
        if not self.stats_data:
            QMessageBox.warning(self, "无数据", "请先执行预览操作")
            return
            
        # 检查操作类型和参数
        if self.modify_radio.isChecked():
            new_value_text = self.new_value_edit.text().strip()
            if not new_value_text:
                QMessageBox.warning(self, "输入错误", "请输入要修改的新厚度值")
                return
                
            try:
                new_value = float(new_value_text)
            except ValueError:
                QMessageBox.warning(self, "格式错误", "请输入有效的数字值")
                return
                
            operation = "modify"
            operation_param = new_value
            operation_type = None  # 修改操作不需要范围类型
        
        # 确定操作类型
        elif self.delete_in_radio.isChecked():
            operation = "delete"
            operation_type = "in_range"  # 删除范围内的点
            operation_param = None
        else:  # self.keep_in_radio.isChecked()
            operation = "delete"
            operation_type = "out_of_range"  # 删除范围外的点
            operation_param = None
        
        # 获取父窗口引用
        parent = self.parent()
        if not hasattr(parent, 'process_batch_files'):
            QMessageBox.critical(self, "错误", "无法访问批量处理功能")
            return
            
        # 获取范围值用于处理
        range_value = None
        if self.selected_method == "relative":
            if self.current_start_point == "max":
                try:
                    range_value = float(self.range_value_edit_max.text())
                except:
                    QMessageBox.warning(self, "输入错误", "请输入有效的范围值")
                    return
            else:
                try:
                    range_value = float(self.range_value_edit_min.text())
                except:
                    QMessageBox.warning(self, "输入错误", "请输入有效的范围值")
                    return
        else:
            range_str = self.range_edit.text().strip()
            range_values = self.parse_range(range_str)
            if not range_values:
                QMessageBox.warning(self, "输入错误", "请输入有效的绝对范围")
                return
            min_val, max_val = range_values
            range_value = (min_val, max_val)
            
        modified_files = parent.process_batch_files(
            self.stats_data, 
            operation, 
            operation_type, 
            self.selected_method,
            self.current_start_point,
            operation_param,
            range_value
        )
            
        if modified_files:
            # 存储修改后的文件列表
            self.modified_files = modified_files
            
            # 显示处理结果
            self.show_results(modified_files)
            
            # 刷新显示
            if hasattr(parent, 'update_display'):
                parent.update_display()
        else:
            QMessageBox.information(self, "结果", "没有文件被修改")
    
    def show_details(self):
        """显示详细信息对话框"""
        if not self.stats_data:
            return
        
        # 创建并显示详细统计对话框
        details_dialog = BatchStatisticsDetailsDialog(self.stats_data, self)
        details_dialog.exec_()
    
    def show_results(self, modified_files):
        """显示处理结果"""
        # 创建结果消息
        msg = f"已处理 {len(modified_files)} 个晶圆文件\n"
        
        # 方法描述
        if self.selected_method == "relative":
            # 相对范围
            if self.current_start_point == "max":
                option = self.max_options.currentText()
                try:
                    range_value = float(self.range_value_edit_max.text())
                    msg += f"相对范围: 从{option}开始(-{range_value:.1f}nm)\n"
                except:
                    msg += f"相对范围: 从{option}开始\n"
            else:
                option = self.min_options.currentText()
                try:
                    range_value = float(self.range_value_edit_min.text())
                    msg += f"相对范围: 从{option}开始(+{range_value:.1f}nm)\n"
                except:
                    msg += f"相对范围: 从{option}开始\n"
        else:
            # 绝对范围
            min_val, max_val = self.parse_range(self.range_edit.text().strip())
            msg += f"绝对范围: {min_val:.1f}nm 至 {max_val:.1f}nm\n"
        
        # 操作描述
        if self.delete_in_radio.isChecked():
            msg += "操作: 删除范围内的数据点\n"
        elif self.keep_in_radio.isChecked():
            msg += "操作: 仅保留范围内的数据点 (删除范围外的点)\n"
        else:
            msg += f"操作: 修改范围内的点值为 {self.new_value_edit.text()} nm\n"
        
        msg += "\n所有修改后的文件已保存为原文件名后追加 'modified'\n"
        msg += "\n处理的文件列表:\n"
        for file_path in modified_files[:10]:  # 只显示前10条
            name = os.path.basename(file_path)
            if len(name) > 30:
                name = name[:27] + "..."
            msg += f"• {name}\n"
        
        if len(modified_files) > 10:
            msg += f"+ {len(modified_files)-10} 更多文件...\n"
        
        # 显示处理结果
        QMessageBox.information(self, "处理完成", msg)

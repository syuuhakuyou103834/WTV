# ui/recipe_analysis_ui.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QFileDialog, QSplitter, QScrollArea, QMessageBox,
    QGroupBox, QComboBox, QDoubleSpinBox, QCheckBox
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
import numpy as np
import os
from core.recipe_engine import RecipeEngine

class RecipeAnalysisUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.engine = RecipeEngine()
        self.speed_image = None
        self.dwell_image = None
        self.current_file = None
        self.circle_mode = False
        self.init_ui()
    
    def init_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # === 镜像翻转设置 ===
        mirror_group = QGroupBox("镜像设置")
        mirror_layout = QHBoxLayout(mirror_group)
        
        self.mirror_btn = QPushButton("沿X轴镜像翻转")
        self.mirror_btn.setToolTip("翻转上下方向 - 顶部变底部，底部变顶部")
        self.mirror_btn.clicked.connect(self.apply_mirror)
        mirror_layout.addWidget(self.mirror_btn)
        
        self.mirror_label = QLabel("当前状态: 未翻转")
        mirror_layout.addWidget(self.mirror_label)
        
        main_layout.addWidget(mirror_group)
        
        # === 圆形区域配置 ===
        circle_group = QGroupBox("圆形区域配置")
        circle_layout = QGridLayout(circle_group)
        
        self.circle_mode_cb = QCheckBox("仅显示圆形区域")
        self.circle_mode_cb.stateChanged.connect(self.toggle_circle_mode)
        circle_layout.addWidget(self.circle_mode_cb, 0, 0, 1, 3)
        
        circle_layout.addWidget(QLabel("直径 (mm):"), 1, 0)
        self.diameter_cb = QComboBox()
        self.diameter_cb.addItems(["100", "150", "200", "300"])
        circle_layout.addWidget(self.diameter_cb, 1, 1)
        self.diameter_cb.setCurrentIndex(1) 
        
        circle_layout.addWidget(QLabel("圆心 X (mm):"), 2, 0)
        self.center_x_input = QDoubleSpinBox()
        self.center_x_input.setDecimals(3)
        self.center_x_input.setRange(-500, 500)
        self.center_x_input.setValue(0)
        circle_layout.addWidget(self.center_x_input, 2, 1)
        
        circle_layout.addWidget(QLabel("圆心 Y (mm):"), 3, 0)
        self.center_y_input = QDoubleSpinBox()
        self.center_y_input.setDecimals(3)
        self.center_y_input.setRange(-500, 500)
        self.center_y_input.setValue(0)
        circle_layout.addWidget(self.center_y_input, 3, 1)
        
        circle_layout.addWidget(QLabel("圆形区域样式:"), 1, 3)
        self.style_cb = QComboBox()
        self.style_cb.addItems(["jet", "plasma", "inferno", "viridis", "coolwarm"])
        self.style_cb.setCurrentText("jet")
        circle_layout.addWidget(self.style_cb, 1, 4)
        
        self.apply_btn = QPushButton("应用圆形设置")
        self.apply_btn.clicked.connect(self.apply_circle_settings)
        circle_layout.addWidget(self.apply_btn, 2, 3, 1, 2)
        
        main_layout.addWidget(circle_group)
        
        # === 文件选择区域 ===
        file_layout = QGridLayout()
        self.file_label = QLabel("Recipe文件: 未选择")
        file_layout.addWidget(QLabel("当前选择:"), 0, 0)
        file_layout.addWidget(self.file_label, 0, 1, 1, 3)
        
        self.select_btn = QPushButton("选择Recipe文件")
        self.select_btn.clicked.connect(self.select_recipe_file)
        file_layout.addWidget(self.select_btn, 1, 0, 1, 4)
        
        main_layout.addLayout(file_layout)
        
        # === 使用分割器显示两张图 ===
        self.splitter = QSplitter(Qt.Horizontal)
        
        # 速度分布区域
        speed_widget = QWidget()
        speed_layout = QVBoxLayout(speed_widget)
        speed_layout.addWidget(QLabel("<b>Y轴速度分布</b>", alignment=Qt.AlignCenter))
        
        self.speed_label = QLabel()
        self.speed_label.setAlignment(Qt.AlignCenter)
        self.speed_label.setMinimumSize(400, 300)
        speed_scroll = QScrollArea()
        speed_scroll.setWidgetResizable(True)
        speed_scroll.setWidget(self.speed_label)
        speed_layout.addWidget(speed_scroll, 1)
        
        speed_layout.addWidget(QLabel("速度矩阵范围 (mm/s): ", alignment=Qt.AlignCenter))
        self.speed_stats_label = QLabel(alignment=Qt.AlignCenter)
        speed_layout.addWidget(self.speed_stats_label)
        
        # 停留时间分布区域
        dwell_widget = QWidget()
        dwell_layout = QVBoxLayout(dwell_widget)
        dwell_layout.addWidget(QLabel("<b>停留时间分布 (1mm网格)</b>", alignment=Qt.AlignCenter))
        
        self.dwell_label = QLabel()
        self.dwell_label.setAlignment(Qt.AlignCenter)
        self.dwell_label.setMinimumSize(400, 300)
        dwell_scroll = QScrollArea()
        dwell_scroll.setWidgetResizable(True)
        dwell_scroll.setWidget(self.dwell_label)
        dwell_layout.addWidget(dwell_scroll, 1)
        
        dwell_layout.addWidget(QLabel("停留时间范围 (s): ", alignment=Qt.AlignCenter))
        self.dwell_stats_label = QLabel(alignment=Qt.AlignCenter)
        dwell_layout.addWidget(self.dwell_stats_label)
        
        self.splitter.addWidget(speed_widget)
        self.splitter.addWidget(dwell_widget)
        self.splitter.setSizes([600, 600])  # 设置初始宽度
        
        # 将分割器放入布局
        main_layout.addWidget(self.splitter, 1)
    
    def toggle_circle_mode(self, state):
        self.circle_mode = state == Qt.Checked
        self.apply_circle_settings()
    
    def apply_mirror(self):
        """应用X轴镜像翻转"""
        # 切换镜像状态
        self.engine.mirror_y = not self.engine.mirror_y
        
        # 更新标签状态
        status = "已翻转" if self.engine.mirror_y else "未翻转"
        self.mirror_label.setText(f"当前状态: {status}")
        
        if self.current_file:
            self.apply_circle_settings()
        else:
            self.parent.update_status_message(f"镜像状态已切换: {status}", "info")
    
    def apply_circle_settings(self):
        if not self.current_file:
            self.parent.update_status_message("请先选择Recipe文件", "warning")
            return
            
        try:
            # 应用圆形设置并重新生成图像
            diameter = float(self.diameter_cb.currentText())
            center_x = self.center_x_input.value()
            center_y = self.center_y_input.value()
            circle_style = self.style_cb.currentText()
            
            self.engine.set_circle_params(diameter, center_x, center_y)
            self.engine.circle_style = circle_style
            self.engine.circle_mode = self.circle_mode
            
            # 处理Recipe文件
            self.speed_file, _, self.dwell_file, _ = self.engine.process_recipe(self.current_file)
            
            # 加载并显示图像
            self.speed_label.setPixmap(QPixmap(self.speed_file))
            self.dwell_label.setPixmap(QPixmap(self.dwell_file))
            
            # 分析并显示统计信息
            self.update_stats()
            
            status = "已翻转" if self.engine.mirror_y else "未翻转"
            msg = f"设置已应用 (镜像: {status}, 圆形: {'开启' if self.circle_mode else '关闭'})"
            self.parent.update_status_message(msg, "success")
        
        except Exception as e:
            self.parent.update_status_message(f"应用设置失败: {str(e)}", "error")
            QMessageBox.critical(self, "应用错误", f"应用设置时出错:\n{str(e)}")
    
    def select_recipe_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择Recipe文件", 
            "", 
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            self.current_file = file_path
            self.parent.update_status_message(f"处理Recipe文件: {os.path.basename(file_path)}")
            
            # 重置镜像状态
            self.engine.mirror_y = False
            self.mirror_label.setText("当前状态: 未翻转")
            
            # 处理Recipe文件
            self.speed_file, _, self.dwell_file, _ = self.engine.process_recipe(file_path)
            
            # 更新UI显示
            self.file_label.setText(f"Recipe文件: {os.path.basename(file_path)}")
            
            # 加载并显示图像
            self.speed_label.setPixmap(QPixmap(self.speed_file))
            self.dwell_label.setPixmap(QPixmap(self.dwell_file))
            
            # 分析并显示统计信息
            self.update_stats()
            
            self.parent.update_status_message(f"Recipe分析完成", "success")
        
        except Exception as e:
            self.parent.update_status_message(f"Recipe分析失败: {str(e)}", "error")
            QMessageBox.critical(self, "处理错误", f"处理Recipe文件时出错:\n{str(e)}")
    
    def update_stats(self):
        """更新显示的统计信息"""
        if self.engine.speed_matrix is None:
            return
            
        try:
            # 获取速度统计
            speed_matrix = self.engine.speed_matrix
            speed_min = np.nanmin(speed_matrix)
            speed_max = np.nanmax(speed_matrix)
            speed_stats = f"{speed_min:.3f} - {speed_max:.3f} mm/s"
            self.speed_stats_label.setText(speed_stats)
            
            # 获取停留时间统计
            dwell_matrix = self.engine.dwell_matrix
            dwell_min = np.nanmin(dwell_matrix)
            dwell_max = np.nanmax(dwell_matrix)
            dwell_stats = f"{dwell_min:.3e} - {dwell_max:.3e} s"
            self.dwell_stats_label.setText(dwell_stats)
        
        except Exception as e:
            self.parent.update_status_message(f"统计信息更新失败: {str(e)}", "warning")

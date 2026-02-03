from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QGridLayout, 
    QLabel, QLineEdit, QPushButton, QCheckBox, QRadioButton,QMessageBox
)
from PyQt5.QtCore import Qt
import numpy as np

class ControlPanel(QGroupBox):
    def __init__(self, parent):
        super().__init__("控制面板", parent)
        self.setFixedWidth(280)
        self.parent = parent
        
        # 主布局
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # 晶圆尺寸设置
        size_group = QGroupBox("晶圆尺寸 (mm)")
        size_layout = QVBoxLayout(size_group)
        
        # 尺寸选项按钮
        sizes = [100, 150, 200, 300]
        self.size_buttons = []
        for size in sizes:
            rb = QRadioButton(f"{size}mm")
            rb.size = size
            rb.toggled.connect(self.update_wafer_size)
            size_layout.addWidget(rb)
            self.size_buttons.append(rb)
        
        # 默认选中200mm
        if len(self.size_buttons) >= 3:
            self.size_buttons[2].setChecked(True)
        
        main_layout.addWidget(size_group)
        
        # 颜色设置
        color_group = QGroupBox("颜色设置")
        color_layout = QGridLayout(color_group)
        
        color_layout.addWidget(QLabel("最小值:"), 0, 0)
        self.vmin_entry = QLineEdit()
        color_layout.addWidget(self.vmin_entry, 0, 1)
        
        color_layout.addWidget(QLabel("最大值:"), 1, 0)
        self.vmax_entry = QLineEdit()
        color_layout.addWidget(self.vmax_entry, 1, 1)
        
        self.apply_btn = QPushButton("应用")
        self.apply_btn.setFixedWidth(80)
        self.apply_btn.clicked.connect(self.apply_color_scale)
        color_layout.addWidget(self.apply_btn, 2, 0)
        
        self.auto_btn = QPushButton("自动")
        self.auto_btn.setFixedWidth(80)
        self.auto_btn.clicked.connect(self.auto_color_scale)
        color_layout.addWidget(self.auto_btn, 2, 1)
        
        main_layout.addWidget(color_group)
        
        # 显示选项
        display_group = QGroupBox("显示选项")
        display_layout = QVBoxLayout(display_group)
        
        self.extend_cb = QCheckBox("扩展晶圆边缘")
        self.extend_cb.toggled.connect(self.toggle_extend_boundary)
        display_layout.addWidget(self.extend_cb)
        
        self.points_cb = QCheckBox("显示数据点")
        self.points_cb.setChecked(True)
        self.points_cb.toggled.connect(self.toggle_scatter_visibility)
        display_layout.addWidget(self.points_cb)
        
        main_layout.addWidget(display_group)
        
        # 统计信息面板
        stats_group = QGroupBox("统计信息")
        stats_layout = QGridLayout(stats_group)
        
        # 统计项标签
        stats_items = [
            ("数据点数", "count"), 
            ("最小值 (nm)", "min"),
            ("最大值 (nm)", "max"),
            ("范围 (nm)", "range"),
            ("平均值 (nm)", "mean"),
            ("标准差 (nm)", "std"),
            ("均一性 (%)", "uniformity")
        ]
        
        self.stat_labels = {}
        for i, (label, key) in enumerate(stats_items):
            stats_layout.addWidget(QLabel(label + ":"), i, 0)
            value_label = QLabel("--")
            stats_layout.addWidget(value_label, i, 1)
            self.stat_labels[key] = value_label
        
        main_layout.addWidget(stats_group)
        
        # 操作按钮
        buttons_group = QGroupBox("操作")
        buttons_layout = QVBoxLayout(buttons_group)
        
        self.add_point_btn = QPushButton("添加数据点")
        self.add_point_btn.clicked.connect(self.parent.add_data_point)
        buttons_layout.addWidget(self.add_point_btn)
        
        self.export_btn = QPushButton("导出数据")
        self.export_btn.clicked.connect(self.parent.export_data)
        buttons_layout.addWidget(self.export_btn)
        
        self.export_img_btn = QPushButton("导出图像")
        self.export_img_btn.clicked.connect(self.parent.export_image)
        buttons_layout.addWidget(self.export_img_btn)
        
        main_layout.addWidget(buttons_group)
    
    def update_wafer_size(self):
        """更新晶圆尺寸"""
        for btn in self.size_buttons:
            if btn.isChecked():
                self.parent.wafer_size = btn.size
                if self.parent.current_data is not None:
                    self.parent.redraw_plot()
                break
    
    def apply_color_scale(self):
        """应用自定义色标"""
        try:
            vmin = float(self.vmin_entry.text()) if self.vmin_entry.text() else None
            vmax = float(self.vmax_entry.text()) if self.vmax_entry.text() else None
            
            self.parent.custom_vmin = vmin
            self.parent.custom_vmax = vmax
            self.parent.redraw_plot()
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数值")
    
    def auto_color_scale(self):
        """使用自动色标"""
        self.vmin_entry.clear()
        self.vmax_entry.clear()
        self.parent.custom_vmin = None
        self.parent.custom_vmax = None
        self.parent.redraw_plot()
    
    def toggle_extend_boundary(self):
        """切换扩展边界模式"""
        self.parent.extend_edge = self.extend_cb.isChecked()
        if self.parent.current_data is not None:
            self.parent.redraw_plot()
    
    def toggle_scatter_visibility(self):
        """切换散点图显示"""
        self.parent.show_scatter = self.points_cb.isChecked()
        if hasattr(self.parent, 'scatter') and self.parent.scatter:
            self.parent.scatter.set_visible(self.parent.show_scatter)
            self.parent.canvas.draw_idle()
    
    def update_stats(self, stats):
        """更新统计信息显示"""
        if not stats:
            for label in self.stat_labels.values():
                label.setText("--")
            return
        
        # 更新所有统计值
        self.stat_labels['count'].setText(str(stats.get('count', 0)))
        self.stat_labels['min'].setText(f"{stats.get('min', 0):.3f}")
        self.stat_labels['max'].setText(f"{stats.get('max', 0):.3f}")
        self.stat_labels['range'].setText(f"{stats.get('max', 0)-stats.get('min', 0):.3f}")
        self.stat_labels['mean'].setText(f"{stats.get('mean', 0):.3f}")
        self.stat_labels['std'].setText(f"{stats.get('std', 0):.3f}")
        
        # 计算并显示均一性
        if 'min' in stats and 'max' in stats and 'mean' in stats and stats['mean'] != 0:
            uni = 100 * (stats['max'] - stats['min']) / (2*stats['mean'])
            self.stat_labels['uniformity'].setText(f"{uni:.2f}")
        else:
            self.stat_labels['uniformity'].setText("--")

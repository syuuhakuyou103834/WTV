import os
import numpy as np
import pandas as pd
import matplotlib as mpl
mpl.use('Qt5Agg')  # 确保使用Qt后端
from PyQt5.QtWidgets import (
    QWidget, QSplitter, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QComboBox, QLineEdit, QSizePolicy, QMessageBox, QFileDialog, QFormLayout
)
from PyQt5.QtGui import QDoubleValidator,QCursor
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.gridspec import GridSpec
from scipy.interpolate import griddata, RBFInterpolator
from matplotlib.colorbar import Colorbar
from matplotlib.patches import Circle
from core.data_processing import load_wafer_data
import matplotlib.font_manager as fm
import platform
import time
import traceback
from PyQt5.QtWidgets import QProgressDialog, QApplication,QMenu,QDialog
from PyQt5.QtCore import Qt, QPoint
from ui.dialogs import NewGridSettingsDialog
from utils.file_io import save_file_dialog
from scipy import spatial

class ThicknessDifferenceCalculator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        
        # 数据存储
        self.wafer_size = 150  # 默认晶圆尺寸 (mm)
        self.data1 = None
        self.data2 = None
        self.data3 = None
        self.result_data = None
        self.grid_x = None
        self.grid_y = None
        self.grid_z1 = None
        self.grid_z2 = None
        self.grid_z3 = None
        self.grid_z_result = None
        self.file_name1 = "未加载文件"
        self.file_name2 = "未加载文件"
        self.file_name3 = "未加载文件"
        self.contours = [None, None, None, None]
        
        # 初始化UI
        self.init_ui()

        self.canvas.mpl_connect('button_press_event', self.on_click)
        
    def init_ui(self):
        # 创建主布局
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建分隔器
        splitter = QSplitter(Qt.Horizontal)
        
        # 创建左侧控制面板
        self.control_panel = self.create_control_panel()
        splitter.addWidget(self.control_panel)
        splitter.setCollapsible(0, False)
        
        # 创建右侧绘图区域容器
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建Matplotlib图表 - 使用2×2网格布局
        self.figure = Figure(figsize=(10, 9), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_layout.addWidget(self.canvas)
        
        # 文件信息标签
        self.file_labels = [
            QLabel(f"文件1: {self.file_name1}"),
            QLabel(f"文件2: {self.file_name2}"),
            QLabel(f"文件3: {self.file_name3}"),
            QLabel("计算结果")
        ]
        
        info_layout = QHBoxLayout()
        for label in self.file_labels:
            info_layout.addWidget(label)
        
        plot_layout.addLayout(info_layout)
        plot_container.setLayout(plot_layout)
        
        splitter.addWidget(plot_container)
        splitter.setCollapsible(1, False)
        main_layout.addWidget(splitter)
        
        # 设置分隔器初始比例
        splitter.setSizes([350, 800])
        
        # 设置中文显示
        self.set_chinese_font()
        
        # 初始绘图
        self.draw_plots()

        # 只在这里连接一次事件
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
    
    def set_chinese_font(self):
        """配置Matplotlib中文字体支持"""
        try:
            if platform.system() == 'Windows':
                font_path = "simhei.ttf" if os.path.exists("simhei.ttf") else None
                if font_path:
                    font_prop = fm.FontProperties(fname=font_path)
                    font_name = font_prop.get_name()
                else:
                    font_name = 'Microsoft YaHei'
                mpl.rcParams['font.sans-serif'] = font_name
            
            mpl.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
        except Exception as e:
            print(f"字体设置错误: {e}")
    
    def create_control_panel(self):
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 掩膜尺寸选择
        size_group = QGroupBox("晶圆掩膜尺寸")
        size_layout = QVBoxLayout()
        
        self.size_combo = QComboBox()
        self.size_combo.addItem("4inch (100mm)", 100)
        self.size_combo.addItem("6inch (150mm)", 150)
        self.size_combo.addItem("8inch (200mm)", 200)
        self.size_combo.setCurrentIndex(1)  # 默认选择6inch
        self.size_combo.currentIndexChanged.connect(self.on_size_changed)
        
        size_layout.addWidget(self.size_combo)
        size_layout.addWidget(QLabel("<i>此尺寸用于可视化显示边界</i>"))
        size_group.setLayout(size_layout)
        
        # 文件操作区
        files_group = QGroupBox("膜厚文件")
        files_layout = QVBoxLayout()
        
        self.load_btn1 = QPushButton("加载文件1")
        self.load_btn1.clicked.connect(lambda: self.load_file(1))
        
        self.load_btn2 = QPushButton("加载文件2")
        self.load_btn2.clicked.connect(lambda: self.load_file(2))
        
        self.load_btn3 = QPushButton("加载文件3")
        self.load_btn3.clicked.connect(lambda: self.load_file(3))
        
        files_layout.addWidget(self.load_btn1)
        files_layout.addWidget(self.load_btn2)
        files_layout.addWidget(self.load_btn3)
        files_group.setLayout(files_layout)
        
        # 系数输入区
        coeff_group = QGroupBox("运算系数")
        coeff_layout = QFormLayout()
        
        self.k1_input = QLineEdit("1.0")
        self.k1_input.setValidator(QDoubleValidator())
        coeff_layout.addRow("系数 k1 (文件2):", self.k1_input)
        
        self.k2_input = QLineEdit("1.0")
        self.k2_input.setValidator(QDoubleValidator())
        coeff_layout.addRow("系数 k2 (文件3):", self.k2_input)
        
        self.calc_btn = QPushButton("执行计算")
        self.calc_btn.clicked.connect(self.calculate_difference)
        coeff_layout.addRow(self.calc_btn)
        
        coeff_group.setLayout(coeff_layout)
        
        # 统计信息面板
        stats_group = QGroupBox("统计信息")
        stats_layout = QVBoxLayout()
        
        # 文件1统计
        file1_stats = QGroupBox("文件1")
        file1_stats_layout = QVBoxLayout()
        
        self.file1_min_label = QLabel("最小值: -")
        self.file1_max_label = QLabel("最大值: -")
        self.file1_mean_label = QLabel("平均值: -")
        self.file1_uniformity_label = QLabel("均一性: -")
        
        file1_stats_layout.addWidget(self.file1_min_label)
        file1_stats_layout.addWidget(self.file1_max_label)
        file1_stats_layout.addWidget(self.file1_mean_label)
        file1_stats_layout.addWidget(self.file1_uniformity_label)
        file1_stats.setLayout(file1_stats_layout)
        
        # 文件2统计
        file2_stats = QGroupBox("文件2")
        file2_stats_layout = QVBoxLayout()
        
        self.file2_min_label = QLabel("最小值: -")
        self.file2_max_label = QLabel("最大值: -")
        self.file2_mean_label = QLabel("平均值: -")
        self.file2_uniformity_label = QLabel("均一性: -")
        
        file2_stats_layout.addWidget(self.file2_min_label)
        file2_stats_layout.addWidget(self.file2_max_label)
        file2_stats_layout.addWidget(self.file2_mean_label)
        file2_stats_layout.addWidget(self.file2_uniformity_label)
        file2_stats.setLayout(file2_stats_layout)
        
        # 文件3统计
        file3_stats = QGroupBox("文件3")
        file3_stats_layout = QVBoxLayout()
        
        self.file3_min_label = QLabel("最小值: -")
        self.file3_max_label = QLabel("最大值: -")
        self.file3_mean_label = QLabel("平均值: -")
        self.file3_uniformity_label = QLabel("均一性: -")
        
        file3_stats_layout.addWidget(self.file3_min_label)
        file3_stats_layout.addWidget(self.file3_max_label)
        file3_stats_layout.addWidget(self.file3_mean_label)
        file3_stats_layout.addWidget(self.file3_uniformity_label)
        file3_stats.setLayout(file3_stats_layout)
        
        # 结果统计
        result_stats = QGroupBox("计算结果")
        result_stats_layout = QVBoxLayout()
        
        self.result_min_label = QLabel("最小值: -")
        self.result_max_label = QLabel("最大值: -")
        self.result_mean_label = QLabel("平均值: -")
        self.result_uniformity_label = QLabel("均一性: -")
        
        result_stats_layout.addWidget(self.result_min_label)
        result_stats_layout.addWidget(self.result_max_label)
        result_stats_layout.addWidget(self.result_mean_label)
        result_stats_layout.addWidget(self.result_uniformity_label)
        result_stats.setLayout(result_stats_layout)
        
        stats_layout.addWidget(file1_stats)
        stats_layout.addWidget(file2_stats)
        stats_layout.addWidget(file3_stats)
        stats_layout.addWidget(result_stats)
        stats_group.setLayout(stats_layout)
        
        # 将所有组件添加到主布局
        layout.addWidget(size_group)
        layout.addWidget(files_group)
        layout.addWidget(coeff_group)
        layout.addWidget(stats_group)
        layout.addStretch(1)  # 添加弹性空间
        
        return panel
    
    def on_size_changed(self):
        """晶圆尺寸改变事件处理"""
        self.wafer_size = self.size_combo.currentData()
        
        # 重新计算网格
        if self.data1 is not None:
            self.grid_x, self.grid_y, self.grid_z1 = self.prepare_grid(self.data1)
        if self.data2 is not None:
            _, _, self.grid_z2 = self.prepare_grid(self.data2)
        if self.data3 is not None:
            _, _, self.grid_z3 = self.prepare_grid(self.data3)
        
        # 如果已经有计算结果，重新计算
        if self.grid_z1 is not None and self.grid_z_result is not None:
            try:
                k1 = float(self.k1_input.text()) if self.k1_input.text() else 0
                k2 = float(self.k2_input.text()) if self.k2_input.text() else 0
                self.calculate_difference()
            except:
                pass
        
        self.draw_plots()
    
    def load_file(self, file_num):
        """加载膜厚文件"""
        # 晶圆尺寸
        wafer_size = self.wafer_size
        
        # 打开文件对话框
        filter = "数据文件 (*.csv *.txt);;所有文件 (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"选择膜厚文件 {file_num}", "", filter
        )
        
        if not file_path:
            return
        
        try:
            # 加载数据
            data, filename_part = load_wafer_data(file_path)
            
            if data is None or len(data) < 3:
                raise ValueError(f"文件至少需要3个有效数据点 ({len(data)} 个)")
            
            if file_num == 1:
                self.data1 = data
                self.file_name1 = os.path.basename(file_path)
                
            elif file_num == 2:
                self.data2 = data
                self.file_name2 = os.path.basename(file_path)
                
            elif file_num == 3:
                self.data3 = data
                self.file_name3 = os.path.basename(file_path)
            
            # 更新文件标签
            self.update_file_labels()
            
            # 生成网格数据（如果是文件1，则生成主网格）
            if file_num == 1:
                self.grid_x, self.grid_y, self.grid_z1 = self.prepare_grid(self.data1)
            elif file_num == 2 and self.grid_x is not None:
                _, _, self.grid_z2 = self.prepare_grid(self.data2)
            elif file_num == 3 and self.grid_x is not None:
                _, _, self.grid_z3 = self.prepare_grid(self.data3)
            
            # 更新统计信息
            self.update_stats(1, self.data1)
            self.update_stats(2, self.data2)
            self.update_stats(3, self.data3)
            
            # 重新绘图
            self.draw_plots()
            
            # 提示信息
            if self.parent_window:
                self.parent_window.update_status_message(f"文件{file_num}已加载: {filename_part}")
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载文件失败:\n{str(e)}")
            
            if self.parent_window:
                self.parent_window.update_status_message(f"文件加载失败: {str(e)}", "error")
    
    def update_file_labels(self):
        """更新文件标签"""
        self.file_labels[0].setText(f"文件1: {self.file_name1}")
        self.file_labels[1].setText(f"文件2: {self.file_name2}")
        self.file_labels[2].setText(f"文件3: {self.file_name3}")
    
    def prepare_grid(self, data):
        """为数据准备网格（插值到标准网格）"""
        if data is None:
            return None, None, None
        
        x, y, z = data[:, 0], data[:, 1], data[:, 2]
        
        # 计算边界（覆盖整个晶圆）
        radius = self.wafer_size / 2
        x_min, x_max = -radius, radius
        y_min, y_max = -radius, radius
        
        # 如果主网格不存在，创建新网格
        if self.grid_x is None:
            self.grid_x, self.grid_y = np.meshgrid(
                np.linspace(x_min, x_max, 200),
                np.linspace(y_min, y_max, 200)
            )
        
        # 使用RBF插值进行高级插值（扩展至边界）
        try:
            # RBF插值 - 能够更好地处理边界
            rbf = RBFInterpolator(  
                np.column_stack([x, y]),
                z,
                kernel='thin_plate_spline',  # 薄板样条核函数
                neighbors=min(50, len(x))   # 使用最邻近的50个点
            )
            
            # 在网格上进行预测
            grid_z = rbf(np.column_stack([self.grid_x.ravel(), self.grid_y.ravel()]))
            grid_z = grid_z.reshape(self.grid_x.shape)
        except Exception as e:
            # 如果RBF插值失败，回退到线性插值
            print(f"RBF插值失败，使用线性插值: {str(e)}")
            try:
                grid_z = griddata((x, y), z, (self.grid_x, self.grid_y), method='linear')
            except:
                # 如果线性插值失败，使用最近邻插值
                grid_z = griddata((x, y), z, (self.grid_x, self.grid_y), method='nearest')
        
        # 应用晶圆边界掩码
        distance = np.sqrt(self.grid_x**2 + self.grid_y**2)
        grid_z[distance > radius] = np.nan
        
        return self.grid_x, self.grid_y, grid_z
    
    def calculate_difference(self):
        """执行膜厚差分运算"""
        # 检查文件1是否已加载
        if self.data1 is None:
            QMessageBox.warning(self, "警告", "请先加载文件1")
            return
        
        # 获取系数
        try:
            k1 = float(self.k1_input.text()) if self.k1_input.text() else 0
            k2 = float(self.k2_input.text()) if self.k2_input.text() else 0
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的系数")
            return
        
        # 确保网格数据有效
        if self.grid_x is None or self.grid_y is None or self.grid_z1 is None:
            QMessageBox.warning(self, "错误", "网格数据无效，请重新加载文件")
            return
        
        # 初始化结果网格为文件1的数据
        self.grid_z_result = self.grid_z1.copy()
        
        # 如果文件2已加载，添加k1 * 文件2
        if self.data2 is not None and self.grid_z2 is not None:
            self.grid_z_result += k1 * self.grid_z2
        
        # 如果文件3已加载，添加k2 * 文件3
        if self.data3 is not None and self.grid_z3 is not None:
            self.grid_z_result += k2 * self.grid_z3
        
        # 创建结果数据点（用于统计）
        valid_mask = ~np.isnan(self.grid_z_result)
        x_valid = self.grid_x[valid_mask].flatten()
        y_valid = self.grid_y[valid_mask].flatten()
        z_valid = self.grid_z_result[valid_mask].flatten()
        self.result_data = np.column_stack((x_valid, y_valid, z_valid))
        
        # 更新结果统计
        self.update_stats(4, self.result_data)
        
        # 重新绘图
        self.draw_plots()
        
        # 提示信息
        k1_str = f"{abs(k1):.3f}" if abs(k1) != 1.0 else ""
        k2_str = f"{abs(k2):.3f}" if abs(k2) != 1.0 else ""
        
        desc = "计算结果："
        if k1 >= 0:
            desc += f"文件1 + {k1_str}×文件2 " if k1_str else "文件1 + 文件2 "
        else:
            desc += f"文件1 - {k1_str}×文件2 " if k1_str else "文件1 - 文件2 "
            
        if k2 >= 0:
            desc += f"+ {k2_str}×文件3" if k2_str else "+ 文件3"
        else:
            desc += f"- {k2_str}×文件3" if k2_str else "- 文件3"
            
        if self.parent_window:
            self.parent_window.update_status_message(desc)
    
    def update_stats(self, panel_num, data):
        """更新统计信息"""
        if data is None or len(data) == 0:
            min_val = max_val = mean_val = uniformity = np.nan
        else:
            thickness = data[:, 2] if data.ndim > 1 else data
            min_val = np.nanmin(thickness) if thickness.size > 0 else np.nan
            max_val = np.nanmax(thickness) if thickness.size > 0 else np.nan
            mean_val = np.nanmean(thickness) if thickness.size > 0 else np.nan
            uniformity = (100* (max_val - min_val) / (2*mean_val) ) if mean_val != 0 else np.nan
        
        if panel_num == 1:  # 文件1
            self.file1_min_label.setText(f"最小值: {min_val:.3f} nm" if not np.isnan(min_val) else "最小值: -")
            self.file1_max_label.setText(f"最大值: {max_val:.3f} nm" if not np.isnan(max_val) else "最大值: -")
            self.file1_mean_label.setText(f"平均值: {mean_val:.3f} nm" if not np.isnan(mean_val) else "平均值: -")
            self.file1_uniformity_label.setText(f"均一性: {uniformity:.2f}%" if not np.isnan(uniformity) else "均一性: -")
        
        elif panel_num == 2:  # 文件2
            self.file2_min_label.setText(f"最小值: {min_val:.3f} nm" if not np.isnan(min_val) else "最小值: -")
            self.file2_max_label.setText(f"最大值: {max_val:.3f} nm" if not np.isnan(max_val) else "最大值: -")
            self.file2_mean_label.setText(f"平均值: {mean_val:.3f} nm" if not np.isnan(mean_val) else "平均值: -")
            self.file2_uniformity_label.setText(f"均一性: {uniformity:.2f}%" if not np.isnan(uniformity) else "均一性: -")
        
        elif panel_num == 3:  # 文件3
            self.file3_min_label.setText(f"最小值: {min_val:.3f} nm" if not np.isnan(min_val) else "最小值: -")
            self.file3_max_label.setText(f"最大值: {max_val:.3f} nm" if not np.isnan(max_val) else "最大值: -")
            self.file3_mean_label.setText(f"平均值: {mean_val:.3f} nm" if not np.isnan(mean_val) else "平均值: -")
            self.file3_uniformity_label.setText(f"均一性: {uniformity:.2f}%" if not np.isnan(uniformity) else "均一性: -")
        
        elif panel_num == 4:  # 结果
            self.result_min_label.setText(f"最小值: {min_val:.3f} nm" if not np.isnan(min_val) else "最小值: -")
            self.result_max_label.setText(f"最大值: {max_val:.3f} nm" if not np.isnan(max_val) else "最大值: -")
            self.result_mean_label.setText(f"平均值: {mean_val:.3f} nm" if not np.isnan(mean_val) else "平均值: -")
            self.result_uniformity_label.setText(f"均一性: {uniformity:.2f}%" if not np.isnan(uniformity) else "均一性: -")
    
    def draw_plots(self):
        """绘制四个区域的图形（带颜色条）"""
        # 清除之前的图形
        self.figure.clear()
        
        # 创建2×2网格布局
        gs = GridSpec(2, 2, figure=self.figure, 
                     height_ratios=[1, 1], 
                     width_ratios=[1, 1])
        
        # 区域1：左上
        ax1 = self.figure.add_subplot(gs[0, 0])
        ax1.set_title("文件1")
        contour1 = self.draw_wafer_plot(ax1, self.grid_z1, self.data1)
        
        # 区域2：右上
        ax2 = self.figure.add_subplot(gs[0, 1])
        ax2.set_title("文件2")
        contour2 = self.draw_wafer_plot(ax2, self.grid_z2, self.data2)
        
        # 区域3：左下
        ax3 = self.figure.add_subplot(gs[1, 0])
        ax3.set_title("文件3")
        contour3 = self.draw_wafer_plot(ax3, self.grid_z3, self.data3)
        
        # 区域4：右下
        ax4 = self.figure.add_subplot(gs[1, 1])
        ax4.set_title("计算结果")
        contour4 = self.draw_wafer_plot(ax4, self.grid_z_result, self.result_data)
        
        # 存储等高线对象用于添加颜色条
        self.contours = [contour1, contour2, contour3, contour4]
        
        # 为每个子图添加颜色条
        for i, ax in enumerate([ax1, ax2, ax3, ax4]):
            if self.contours[i] is not None:
                cbar = self.figure.colorbar(self.contours[i], ax=ax, fraction=0.046, pad=0.04)
                cbar.set_label('厚度 (nm)')
        
        # 更新画布
        self.canvas.draw()

        
    
    def draw_wafer_plot(self, ax, grid_z, raw_data):
        """在指定轴上绘制晶圆图，返回contour对象"""
        # 清除之前的图形
        ax.clear()
        
        if grid_z is None and raw_data is None:
            # 没有数据时显示提示信息
            ax.text(0.5, 0.5, "无数据", 
                   horizontalalignment='center',
                   verticalalignment='center',
                   transform=ax.transAxes,
                   fontsize=14)
            return None
        
        radius = self.wafer_size / 2
        
        if grid_z is not None and not np.isnan(grid_z).all():
            # 使用网格数据绘制等高线图
            # 检查有效数据
            valid_values = grid_z[~np.isnan(grid_z)]
            if len(valid_values) > 0:
                vmin = np.min(valid_values)
                vmax = np.max(valid_values)
            else:
                vmin = 0
                vmax = 100
            
            # 绘制等高线图
            contour = ax.contourf(
                self.grid_x, self.grid_y, grid_z, 
                levels=50, 
                cmap='jet',
                extend='both',
                vmin=vmin,
                vmax=vmax
            )
            
        elif raw_data is not None and len(raw_data) > 0:
            # 如果有原始数据但没有网格数据，直接绘制散点图
            x, y, thickness = raw_data[:, 0], raw_data[:, 1], raw_data[:, 2]
            
            # 绘制散点
            contour = ax.scatter(x, y, c=thickness, s=30, 
                               cmap='jet', alpha=0.8)
        else:
            # 没有数据时显示提示信息
            ax.text(0.5, 0.5, "无数据", 
                   horizontalalignment='center',
                   verticalalignment='center',
                   transform=ax.transAxes,
                   fontsize=14)
            return None
        
        # 添加晶圆边界
        wafer = Circle((0, 0), radius, edgecolor='black', fill=False, linewidth=1.5)
        ax.add_patch(wafer)
        
        # 设置轴属性
        ax.set_xlabel("X 坐标 (mm)")
        ax.set_ylabel("Y 坐标 (mm)")
        ax.set_aspect('equal')
        ax.grid(True, linestyle='--', alpha=0.3)
        
        # 设置坐标轴范围
        ax.set_xlim(-radius * 1.1, radius * 1.1)
        ax.set_ylim(-radius * 1.1, radius * 1.1)
        
        return contour
    
    def on_click(self, event):
        """处理鼠标点击事件 - 主要用于右击菜单"""
        if hasattr(event, 'inaxes') and event.inaxes is not None:
            # 打印坐标轴标题以便调试
            # print(f"Clicked on: {event.inaxes.get_title()}")
            
            if event.button == 3:  # 右键点击
                if event.inaxes.get_title() == "计算结果":
                    # 获取鼠标在屏幕坐标的绝对位置
                    abs_pos = self.canvas.mapToGlobal(QPoint(event.x, event.y))
                    
                    # 创建右击菜单
                    menu = QMenu(self)
                    menu.addAction("导出计算后的网格结果至指定坐标", self.export_calculated_grid)
                    
                    # 显示菜单
                    menu.exec_(abs_pos)

    def mousePressEvent(self, event):
        """全局鼠标按下事件处理"""
        if event.button() == Qt.RightButton:
            # 在组件任何位置右键点击都弹出菜单
            self.show_context_menu(QCursor.pos())
    
    def on_mouse_press(self, event):
        """处理画布上的鼠标点击事件"""
        if event.button == 3:  # 右键点击
            if event.inaxes is not None:
                # 打印坐标轴标题以便调试
                print(f"Clicked on: {event.inaxes.get_title().strip()}")
                
                if event.inaxes.get_title().strip() == "计算结果":
                    # 直接在点击位置显示菜单
                    self.show_context_menu(self.canvas.mapToGlobal(QPoint(event.x, event.y)))
                else:
                    # 其他区域也显示菜单（根据需求可选）
                    self.show_context_menu(self.canvas.mapToGlobal(QPoint(event.x, event.y)))
            else:
                # 在画布上但不在坐标轴区域
                self.show_context_menu(self.canvas.mapToGlobal(QPoint(event.x, event.y)))
    
    def show_context_menu(self, pos):
        """显示上下文菜单 - 优化版"""
        menu = QMenu(self)
        
        # 总是添加导出选项
        menu.addAction("导出计算结果至指定坐标", self.export_calculated_grid)
        
        # 仅当有计算结果时显示其他操作项
        if self.grid_z_result is not None:
            menu.addAction("导出计算数据原始格式", self.export_raw_result)
            menu.addAction("保存当前计算结果图", self.save_current_plot)
        
        # 添加基本信息
        if self.grid_z_result is not None:
            stats = self.calculate_stats(self.result_data)
            info_action = menu.addAction(
                f"平均厚度: {stats['mean']:.1f}nm 均匀性: {stats['uni']:.2f}%"
            )
            info_action.setEnabled(False)  # 不可点击的纯信息
        
        # 显示菜单
        menu.exec_(pos)
    
    def export_raw_result(self):
        """导出原始计算结果数据"""
        if self.result_data is None:
            return
        
        save_path = save_file_dialog(
            "保存计算结果",
            default_path="raw_calculated_data.csv",
            filter="CSV文件 (*.csv)"
        )
        
        if save_path:
            try:
                df = pd.DataFrame(self.result_data, columns=["X [mm]", "Y [mm]", "Thickness [nm]"])
                df.to_csv(save_path, index=False)
                QMessageBox.information(self, "导出成功", "原始计算结果数据已导出")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"无法保存文件: {str(e)}")
    
    def save_current_plot(self):
        """保存当前绘图"""
        save_path = save_file_dialog(
            "保存当前绘图",
            default_path="thickness_difference_plot.png",
            filter="PNG图像 (*.png)"
        )
        
        if save_path:
            try:
                self.figure.savefig(save_path, dpi=300)
                QMessageBox.information(self, "保存成功", "当前绘图已保存")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"无法保存图像: {str(e)}")
    
    def calculate_stats(self, data):
        """计算统计信息"""
        if data is None or len(data) == 0:
            return {"min": 0, "max": 0, "mean": 0, "uni": 0}
        
        thickness = data[:, 2]
        min_val = np.nanmin(thickness)
        max_val = np.nanmax(thickness)
        mean_val = np.nanmean(thickness)
        uniformity = (100 * (max_val - min_val) / (2 * mean_val) )if mean_val != 0 else 0
        
        return {
            "min": min_val,
            "max": max_val,
            "mean": mean_val,
            "uni": uniformity
        }
    
    # 保留原有的export_calculated_grid方法
    
    def export_calculated_grid(self):
        """导出计算结果到指定的新坐标网格"""
        start_time = time.time()
        print(f"[DEBUG] 开始导出计算结果网格 @ {time.ctime()}")
        
        # 检查是否有计算结果
        if self.grid_z_result is None or self.result_data is None:
            QMessageBox.warning(self, "无计算结果", "请先计算得到结果后再导出")
            print("[ERROR] 导出失败: 无计算结果")
            return
            
        try:
            # 打开设置对话框
            dlg = NewGridSettingsDialog(self.wafer_size, self)
            if dlg.exec_() != QDialog.Accepted:
                print("[DEBUG] 用户取消导出")
                return
            
            # 获取设置
            x_step, y_step, start_point = dlg.result
            x_start, y_start = start_point
            
            # 验证步长
            if x_step <= 0 or y_step <= 0:
                QMessageBox.warning(self, "输入错误", "步长必须大于0")
                return
            
            print(f"[DEBUG] 新网格设置 - X步长: {x_step}, Y步长: {y_step}, 起始点: {x_start},{y_start}")
            
            # 计算网格范围
            wafer_radius = self.wafer_size / 2
            safe_radius = wafer_radius * 0.99  # 安全边界
            
            # 生成x坐标序列
            x_coords = []
            current_x = x_start
            
            # 向右扩展
            while current_x <= safe_radius:
                x_coords.append(current_x)
                current_x += x_step
            
            # 向左扩展
            current_x = x_start - x_step
            while current_x >= -safe_radius:
                x_coords.append(current_x)
                current_x -= x_step
            
            # 排序并去重
            x_coords = sorted(set(x_coords))
            
            # 生成y坐标序列
            y_coords = []
            current_y = y_start
            
            # 向上扩展
            while current_y <= safe_radius:
                y_coords.append(current_y)
                current_y += y_step
            
            # 向下扩展
            current_y = y_start - y_step
            while current_y >= -safe_radius:
                y_coords.append(current_y)
                current_y -= y_step
            
            # 排序并去重
            y_coords = sorted(set(y_coords))
            
            print(f"[DEBUG] 生成新网格: X点数={len(x_coords)}, Y点数={len(y_coords)}")
            
            # 显示进度对话框
            progress_dialog = QProgressDialog("生成新网格数据...", "取消", 0, len(y_coords), self)
            progress_dialog.setWindowTitle("导出计算结果")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(1000)
            
            # 生成网格
            total_points = len(x_coords) * len(y_coords)
            print(f"[PERF] 将生成约 {total_points} 个数据点")
            
            generated_points = 0
            valid_points = 0
            new_data = []
            
            try:
                for i, y in enumerate(y_coords):
                    if progress_dialog.wasCanceled():
                        print("[DEBUG] 用户取消导出")
                        return
                        
                    progress_dialog.setValue(i)
                    QApplication.processEvents()  # 确保UI响应
                    
                    for x in x_coords:
                        generated_points += 1
                        
                        # 检查点是否在晶圆内
                        distance = np.sqrt(x**2 + y**2)
                        if distance <= wafer_radius:
                            # 使用最近邻值（网格数据已经是计算结果）
                            x_index = np.abs(self.grid_x[0] - x).argmin()
                            y_index = np.abs(self.grid_y[:,0] - y).argmin()
                            
                            # 提取厚度值
                            thickness = self.grid_z_result[y_index, x_index]
                            
                            # 防止NaN值
                            if not np.isnan(thickness):
                                new_data.append([x, y, thickness])
                                valid_points += 1
            except Exception as e:
                print(f"[ERROR] 生成网格时出错: {str(e)}")
                traceback.print_exc()
                QMessageBox.critical(self, "内部错误", f"生成新网格失败: {str(e)}")
                return
            
            progress_dialog.close()
            
            if not new_data:
                QMessageBox.warning(self, "错误", "未能生成有效数据")
                print("[ERROR] 没有可用的数据点")
                return
                
            # 转换为NumPy数组
            new_data = np.array(new_data)
            
            print(f"[STATS] 生成的有效数据点: {valid_points}/{generated_points} ({valid_points/generated_points:.1%})")
            
            # 保存文件
            save_path = save_file_dialog(
                "保存计算结果数据",
                default_path="calculated_thickness.csv",
                filter="CSV文件 (*.csv)"
            )
            
            if not save_path:
                print("[DEBUG] 用户取消保存")
                return
            
            try:
                # 使用Pandas保存，确保数据完整性
                import pandas as pd
                df = pd.DataFrame(new_data, columns=["X [mm]", "Y [mm]", "Thickness [nm]"])
                df.to_csv(save_path, index=False)
                
                elapsed = time.time() - start_time
                print(f"[SUCCESS] 导出完成! 文件名: {save_path}, 耗时: {elapsed:.2f}秒")
                
                QMessageBox.information(self, "导出成功", 
                                    f"已成功导出计算网格数据至 {os.path.basename(save_path)}\n"
                                    f"生成数据点: {valid_points} 个")
            except Exception as e:
                print(f"[ERROR] 保存文件失败: {str(e)}")
                QMessageBox.critical(self, "保存失败", f"无法保存文件: {str(e)}")
        except Exception as e:
            print(f"[CRITICAL] 导出过程中发生错误: {str(e)}")
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

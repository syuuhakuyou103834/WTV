import sys
from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
    QStatusBar, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from .single_wafer_ui import SingleWaferUI
from .batch_wafer_ui import BatchWaferUI
from .menu_bar import create_menu_bar
from ui.batch_statistics_dialog import BatchStatisticsDialog
import os
from ui.recipe_analysis_ui import RecipeAnalysisUI
from ui.convolution_integral_ui import ConvolutionIntegralUI
from ui.etching_simulation_ui import EtchingSimulationUI
from ui.thickness_difference_calculator_ui import ThicknessDifferenceCalculator

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("晶圆膜厚可视化工具 WTV-4.2.1 20251125 powered by Zhou Boyang")
        self.setGeometry(100, 100, 1200, 800)

        # 尝试加载应用程序图标
        icon_paths = [
            "WTV_icon.ico",  # 开发环境中
            os.path.join(os.getcwd(), "WTV_icon.ico"),  # 打包后同级目录
            os.path.join(os.path.dirname(__file__), "WTV_icon.ico"), # 打包后的路径
            os.path.join(getattr(sys, '_MEIPASS', ""), "WTV_icon.ico")  # PyInstaller 资源路径
        ]
        
        icon = None
        for path in icon_paths:
            if os.path.exists(path):
                try:
                    icon = QIcon(path)
                    print(f"[MainWindow] 加载图标: {path}")
                    self.setWindowIcon(icon)  # 关键修复：使用局部变量
                    break
                except Exception as e:
                    print(f"[MainWindow] 图标加载失败: {e}")
        
        # 创建中心部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 创建单页UI实例
        self.single_wafer_tab = SingleWaferUI(parent=self)
        self.tab_widget.addTab(self.single_wafer_tab, "单片晶圆可视化")
        
        # 创建批量处理UI实例
        self.batch_wafer_tab = BatchWaferUI(parent=self)
        self.tab_widget.addTab(self.batch_wafer_tab, "批量晶圆处理")

        # 创建Recipe分析UI实例
        self.recipe_analysis_tab = RecipeAnalysisUI(parent=self)
        self.tab_widget.addTab(self.recipe_analysis_tab, "Recipe分析")  

        # +++ 新增卷积积分标签页 +++
        self.convolution_tab = ConvolutionIntegralUI(parent=self)
        self.tab_widget.addTab(self.convolution_tab, "刻蚀深度分布计算")

        # 创建刻蚀模拟UI实例
        self.etching_sim_tab = EtchingSimulationUI(parent=self)
        self.tab_widget.addTab(self.etching_sim_tab, "刻蚀模拟")

        # +++ 膜厚差分运算组件 +++
        self.thickness_diff_tab = ThicknessDifferenceCalculator(parent=self)
        self.tab_widget.addTab(self.thickness_diff_tab, "膜厚差分运算")
        
        # 创建菜单栏
        self.menu_bar = create_menu_bar(self)
        self.setMenuBar(self.menu_bar)
        
        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")

    def show_batch_statistics(self):
        """显示批量统计对话框"""
        if not hasattr(self, 'batch_wafer_tab') or not self.batch_wafer_tab.files_data:
            QMessageBox.information(self, "提示", "请先在批量处理页面加载数据")
            return

        # 获取批量处理页面的晶圆数据
        wafer_data = self.batch_wafer_tab.files_data

        # 创建并显示统计对话框
        self.batch_stats_dialog = BatchStatisticsDialog(wafer_data, self)
        self.batch_stats_dialog.show()

    def trigger_batch_outlier_removal(self):
        """触发批量异常值再次剔除（菜单栏调用）"""
        if not hasattr(self, 'batch_wafer_tab') or not self.batch_wafer_tab.files_data:
            QMessageBox.information(self, "提示", "请先在批量处理页面加载数据")
            return

        # 调用批量处理页面的异常值检测方法
        self.batch_wafer_tab.trigger_outlier_detection()
    
    def update_status_message(self, message, msg_type="info"):
        """更新状态栏消息"""
        if msg_type == "error":
            self.statusBar.showMessage(message, 10000)
            self.statusBar.setStyleSheet("background-color: #ffdddd; color: #cc0000;")
        else:
            self.statusBar.showMessage(message, 5000)
            self.statusBar.setStyleSheet("")

    def batch_point_edit(self):
        """显示批量数据点处理窗口"""
        if hasattr(self, 'batch_wafer_tab') and self.batch_wafer_tab:
            self.batch_wafer_tab.show_batch_point_edit()
        else:
            QMessageBox.warning(self, "不可用", "请先进入批量处理页面")
    
    def load_data(self):
        self.single_wafer_tab.load_data()
    
    def export_data(self):
        self.single_wafer_tab.export_data()
    
    def export_image(self):
        self.single_wafer_tab.export_image()
    
    def add_data_point(self):
        self.single_wafer_tab.add_data_point()
    
    def select_by_thickness_range(self):
        self.single_wafer_tab.select_by_thickness_range()
    
    def toggle_extend_boundary(self):
        self.single_wafer_tab.toggle_boundary()
    
    def toggle_scatter_visibility(self):
        self.single_wafer_tab.toggle_scatter_visibility()
    
    def toggle_distribution_stats(self):
        self.single_wafer_tab.toggle_distribution_stats()

    def export_to_new_coords(self):
        self.single_wafer_tab.export_to_new_coords()

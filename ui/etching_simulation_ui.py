import os
import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFileDialog, QMessageBox,
    QGroupBox, QSizePolicy, QComboBox, QSplitter,
    QSizePolicy, QSpinBox, QDoubleSpinBox, QScrollArea,
    QTabWidget, QFrame, QScrollArea, QProgressDialog
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from core.etching_processor import IonBeamProcessor
from core.outlier_processor import OutlierProcessor
from PyQt5.QtCore import QThread, pyqtSignal
import pandas as pd
from ui.dialogs import AdvancedOptionsDialog
from core.config_manager import get_config_manager
from core.simulation_logger import SimulationLogger

class EtchingSimulationUI(QWidget):
    """刻蚀模拟和停留时间计算界面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.etching_file = None
        self.beam_file = None
        self.output_dir = None
        self.processor = IonBeamProcessor()
        self.stat_labels = {}  
        # 跟踪每个坐标轴的colorbar对象
        self.colorbars = {}

        # 从配置管理器加载高级选项参数
        config_manager = get_config_manager()
        self.transition_width = config_manager.get_transition_width()
        self.recipe_range = config_manager.get_recipe_range()
        self.uniformity_threshold = config_manager.get_uniformity_threshold()
        self.speed_threshold = config_manager.get_speed_threshold()

        # 初始化异常值处理器
        self.outlier_processor = OutlierProcessor(self, self.main_window, self.uniformity_threshold)

        # 模拟过程统计变量
        self.simulation_count = 1  # 模拟次数，初始为1
        self.outlier_removal_count = 0  # 异常值剔除次数
        self.total_removed_points = 0  # 已剔除异常点总数
        self.original_data_count = 0  # 原始数据点数，用于计算

        # 批量处理相关变量
        self.batch_file_list = []  # 批量处理的文件列表
        self.current_batch_index = 0  # 当前处理的文件索引
        self.is_batch_processing = False  # 是否正在进行批量处理
        self.batch_processor = None  # 批量处理器对象

        # 初始化UI
        self.init_ui()
    
    def init_ui(self):
        """初始化用户界面 - 使用左右分栏布局"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)
        
        # 创建分隔条 (可拖动调整大小)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(8)
        self.splitter.setStyleSheet("""
            QSplitter::handle:horizontal {
                background: #d0d0d0;
                border: 1px solid #b0b0b0;
            }
            QSplitter::handle:hover {
                background: #90c0ff;
            }
        """)
        
        # === 左侧控制面板 ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(10)
        
        # === 输入参数区域 ===
        param_group = QGroupBox("刻蚀模拟参数")
        param_group.setFont(QFont("Arial", 10, QFont.Bold))
        param_layout = QGridLayout(param_group)
        param_layout.setSpacing(6)
        param_layout.setColumnMinimumWidth(1, 120)
        
        param_layout.addWidget(QLabel("模拟网格尺寸 (mm):"), 0, 0)
        self.grid_size_combo = QComboBox()
        self.grid_size_combo.addItems(["150", "160", "170","180", "200","240","300"])
        self.grid_size_combo.setCurrentIndex(5)  # 默认240
        self.grid_size_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        param_layout.addWidget(self.grid_size_combo, 0, 1, 1, 2)
        
        param_layout.addWidget(QLabel("分辨率 (mm/pixel):"), 1, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["0.5", "1.0", "2.0"])
        self.resolution_combo.setCurrentIndex(1)  # 默认1.0
        self.resolution_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        param_layout.addWidget(self.resolution_combo, 1, 1, 1, 2)
        
        param_layout.addWidget(QLabel("晶圆直径 (mm):"), 2, 0)
        self.wafer_diameter_combo = QComboBox()
        self.wafer_diameter_combo.addItems(["100", "150", "200"])
        self.wafer_diameter_combo.setCurrentIndex(1)  # 默认150
        self.wafer_diameter_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        param_layout.addWidget(self.wafer_diameter_combo, 2, 1, 1, 2)
        
        param_layout.addWidget(QLabel("目标膜厚 (nm):"), 3, 0)
        self.target_thickness_input = QDoubleSpinBox()
        self.target_thickness_input.setRange(10, 10000)
        self.target_thickness_input.setValue(1800)
        self.target_thickness_input.setSingleStep(10)
        self.target_thickness_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        param_layout.addWidget(self.target_thickness_input, 3, 1, 1, 2)

        # 新增载台中心点输入 - 从配置文件加载初始值
        config_manager = get_config_manager()

        param_layout.addWidget(QLabel("载台中心X (mm):"), 4, 0)
        self.stage_center_x = QDoubleSpinBox()
        self.stage_center_x.setRange(-100, 100)
        self.stage_center_x.setValue(config_manager.get_stage_center_x())
        self.stage_center_x.setSingleStep(1.0)
        param_layout.addWidget(self.stage_center_x, 4, 1, 1, 2)

        param_layout.addWidget(QLabel("载台中心Y (mm):"), 5, 0)
        self.stage_center_y = QDoubleSpinBox()
        self.stage_center_y.setRange(-200, 200)
        self.stage_center_y.setValue(config_manager.get_stage_center_y())
        self.stage_center_y.setSingleStep(1.0)
        param_layout.addWidget(self.stage_center_y, 5, 1, 1, 2)

        # 添加信号连接：当载台中心坐标改变时自动保存到配置文件
        self.stage_center_x.valueChanged.connect(self._save_stage_center_config)
        self.stage_center_y.valueChanged.connect(self._save_stage_center_config)

        # 新增: y-Step步长选择
        param_layout.addWidget(QLabel("y-Step步长:"), 6, 0)  # 新行，在第6行
        self.y_step_combo = QComboBox()
        self.y_step_combo.addItems(["1", "2", "3"])
        self.y_step_combo.setCurrentIndex(1)  # 默认2
        self.y_step_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        param_layout.addWidget(self.y_step_combo, 6, 1, 1, 2)

        # 高级选项按钮
        self.advanced_btn = QPushButton("高级选项")
        self.advanced_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:pressed {
                background-color: #e65100;
            }
        """)
        self.advanced_btn.clicked.connect(self.show_advanced_options)
        param_layout.addWidget(self.advanced_btn, 7, 0, 1, 3)

        left_layout.addWidget(param_group)

        # === 文件选择区域 ===
        file_group = QGroupBox("文件选择")
        file_group.setFont(QFont("Arial", 10, QFont.Bold))
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(6)
        
        # 膜厚文件选择
        etch_layout = QVBoxLayout()
        etch_layout.addWidget(QLabel("初始膜厚数据文件:"))
        
        sub_layout = QHBoxLayout()
        self.etching_label = QLabel("未选择")
        self.etching_label.setWordWrap(True)  # 启用自动换行
        self.etching_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.etching_label.setStyleSheet("""
            QLabel {
                color: #555555; 
                background-color: #f0f0f0;
                border-radius: 3px;
                padding: 3px;
            }
        """)
        sub_layout.addWidget(self.etching_label)
        
        self.select_etching_btn = QPushButton("选择...")
        self.select_etching_btn.setFixedWidth(80)
        self.select_etching_btn.setStyleSheet("padding: 3px;")
        self.select_etching_btn.clicked.connect(self.select_etching_data)
        sub_layout.addWidget(self.select_etching_btn)
        
        etch_layout.addLayout(sub_layout)
        file_layout.addLayout(etch_layout)
        
        # 离子束文件选择
        beam_layout = QVBoxLayout()
        beam_layout.addWidget(QLabel("离子束分布文件:"))
        
        sub_layout = QHBoxLayout()
        self.beam_label = QLabel("未选择")
        self.beam_label.setWordWrap(True)  # 启用自动换行
        self.beam_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.beam_label.setStyleSheet("""
            QLabel {
                color: #555555; 
                background-color: #f0f0f0;
                border-radius: 3px;
                padding: 3px;
            }
        """)
        sub_layout.addWidget(self.beam_label)
        
        self.select_beam_btn = QPushButton("选择...")
        self.select_beam_btn.setFixedWidth(80)
        self.select_beam_btn.setStyleSheet("padding: 3px;")
        self.select_beam_btn.clicked.connect(self.select_beam_profile)
        sub_layout.addWidget(self.select_beam_btn)
        
        beam_layout.addLayout(sub_layout)
        file_layout.addLayout(beam_layout)
        
        # 输出目录选择
        output_layout = QVBoxLayout()
        output_layout.addWidget(QLabel("输出目录:"))
        
        sub_layout = QHBoxLayout()
        self.output_label = QLabel("未选择")
        self.output_label.setWordWrap(True)  # 启用自动换行
        self.output_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.output_label.setStyleSheet("""
            QLabel {
                color: #555555; 
                background-color: #f0f0f0;
                border-radius: 3px;
                padding: 3px;
            }
        """)
        sub_layout.addWidget(self.output_label)
        
        self.select_output_btn = QPushButton("选择...")
        self.select_output_btn.setFixedWidth(80)
        self.select_output_btn.setStyleSheet("padding: 3px;")
        self.select_output_btn.clicked.connect(self.select_output_dir)
        sub_layout.addWidget(self.select_output_btn)
        
        output_layout.addLayout(sub_layout)
        file_layout.addLayout(output_layout)
        
        left_layout.addWidget(file_group, 1)
        
        # === 统计数据区域 ===
        stats_group = QGroupBox("膜厚统计")
        stats_group.setFont(QFont("Arial", 10, QFont.Bold))
        stats_layout = QGridLayout(stats_group)
        stats_layout.setHorizontalSpacing(10)
        stats_layout.setVerticalSpacing(6)
        
        # 创建标签并存储引用
        stats_layout.addWidget(QLabel("区域"), 0, 0)
        stats_layout.addWidget(QLabel("初始膜厚"), 0, 1)
        stats_layout.addWidget(QLabel("目标膜厚"), 0, 2)
        stats_layout.addWidget(QLabel("刻蚀后膜厚"), 0, 3)
        stats_layout.addWidget(QLabel("刻蚀量"), 0, 4)
        
        stats_layout.addWidget(QLabel("最小值 (nm):"), 1, 0)
        self.stat_labels['min_initial'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['min_initial'], 1, 1)
        self.stat_labels['min_target'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['min_target'], 1, 2)
        self.stat_labels['min_result'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['min_result'], 1, 3)
        self.stat_labels['min_etch'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['min_etch'], 1, 4)
        
        stats_layout.addWidget(QLabel("最大值 (nm):"), 2, 0)
        self.stat_labels['max_initial'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['max_initial'], 2, 1)
        self.stat_labels['max_target'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['max_target'], 2, 2)
        self.stat_labels['max_result'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['max_result'], 2, 3)
        self.stat_labels['max_etch'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['max_etch'], 2, 4)
        
        stats_layout.addWidget(QLabel("平均值 (nm):"), 3, 0)
        self.stat_labels['mean_initial'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['mean_initial'], 3, 1)
        self.stat_labels['mean_target'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['mean_target'], 3, 2)
        self.stat_labels['mean_result'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['mean_result'], 3, 3)
        self.stat_labels['mean_etch'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['mean_etch'], 3, 4)
        
        stats_layout.addWidget(QLabel("范围 (nm):"), 4, 0)
        self.stat_labels['range_initial'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['range_initial'], 4, 1)
        self.stat_labels['range_target'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['range_target'], 4, 2)
        self.stat_labels['range_result'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['range_result'], 4, 3)
        self.stat_labels['range_etch'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['range_etch'], 4, 4)
        
        stats_layout.addWidget(QLabel("均一性 (%):"), 5, 0)
        self.stat_labels['uniformity_initial'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['uniformity_initial'], 5, 1)
        self.stat_labels['uniformity_target'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['uniformity_target'], 5, 2)
        self.stat_labels['uniformity_result'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['uniformity_result'], 5, 3)
        self.stat_labels['uniformity_etch'] = QLabel("--")
        stats_layout.addWidget(self.stat_labels['uniformity_etch'], 5, 4)
        
        # 设置标签样式
        for label in self.stat_labels.values():
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("""
                font-weight: bold; 
                background-color: #f8f8f8;
                border: 1px solid #e0e0e0;
                border-radius: 3px;
                padding: 2px;
            """)
            
        for row in range(1, 6):
            for col in range(1, 5):
                item = stats_layout.itemAtPosition(row, col)
                if item and item.widget():
                    item.widget().setStyleSheet("text-align: center;")
        
        left_layout.addWidget(stats_group, 1)

        # === 模拟过程统计区域 ===
        process_stats_group = QGroupBox("模拟过程统计")
        process_stats_group.setFont(QFont("Arial", 10, QFont.Bold))
        process_stats_layout = QGridLayout(process_stats_group)
        process_stats_layout.setHorizontalSpacing(10)
        process_stats_layout.setVerticalSpacing(6)  # 与刻蚀模拟参数保持一致的行间距

        # 创建模拟过程统计标签
        self.process_stat_labels = {}

        # 模拟次数
        process_stats_layout.addWidget(QLabel("模拟次数:"), 0, 0)
        self.process_stat_labels['simulation_count'] = QLabel("1")
        self.process_stat_labels['simulation_count'].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.process_stat_labels['simulation_count'].setStyleSheet("""
            font-weight: bold;
            background-color: #e8f5e8;
            border: 1px solid #c3e6c3;
            border-radius: 3px;
            padding: 2px 8px;
        """)
        process_stats_layout.addWidget(self.process_stat_labels['simulation_count'], 0, 1)

        # 异常值剔除次数
        process_stats_layout.addWidget(QLabel("异常值剔除次数:"), 1, 0)
        self.process_stat_labels['outlier_removal_count'] = QLabel("0")
        self.process_stat_labels['outlier_removal_count'].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.process_stat_labels['outlier_removal_count'].setStyleSheet("""
            font-weight: bold;
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 3px;
            padding: 2px 8px;
        """)
        process_stats_layout.addWidget(self.process_stat_labels['outlier_removal_count'], 1, 1)

        # 已剔除异常点个数
        process_stats_layout.addWidget(QLabel("已剔除异常点个数:"), 2, 0)
        self.process_stat_labels['total_removed_points'] = QLabel("0")
        self.process_stat_labels['total_removed_points'].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.process_stat_labels['total_removed_points'].setStyleSheet("""
            font-weight: bold;
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 3px;
            padding: 2px 8px;
        """)
        process_stats_layout.addWidget(self.process_stat_labels['total_removed_points'], 2, 1)

        left_layout.addWidget(process_stats_group, 1)

        # === 控制按钮区域 ===
        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(0, 10, 0, 5)
        btn_layout.addSpacing(10)
        
        self.process_btn = QPushButton("开始模拟")
        self.process_btn.setMinimumHeight(42)
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #66bb6a;
            }
            QPushButton:pressed {
                background-color: #388e3c;
            }
            QPushButton:disabled {
                background-color: #a5d6a7;
            }
        """)
        self.process_btn.clicked.connect(self.run_simulation)

        # 新增生成载台运动速度按钮
        self.generate_stage_speed_btn = QPushButton("生成载台运动速度Recipe")
        self.generate_stage_speed_btn.setMinimumHeight(42)
        self.generate_stage_speed_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e88e5;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #42a5f5;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
            QPushButton:disabled {
                background-color: #90caf9;
            }
        """)
        self.generate_stage_speed_btn.clicked.connect(self.generate_stage_speed_map)

        # 添加响应式布局
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.process_btn)

        # === 运动速度Recipe统计 ===
        recipe_stats_group = QGroupBox("运动速度Recipe统计")
        recipe_stats_group.setFont(QFont("Arial", 10, QFont.Bold))
        recipe_stats_layout = QGridLayout(recipe_stats_group)
        recipe_stats_layout.setHorizontalSpacing(10)
        recipe_stats_layout.setVerticalSpacing(6)  # 与模拟过程统计保持一致的行间距

        # Recipe行数显示
        recipe_rows_label = QLabel("Recipe行数:")
        self.recipe_rows_value = QLabel("--")
        self.recipe_rows_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.recipe_rows_value.setStyleSheet("""
            font-weight: bold;
            background-color: #e8f5e8;
            border: 1px solid #c3e6c3;
            border-radius: 3px;
            padding: 2px 8px;
        """)
        recipe_stats_layout.addWidget(recipe_rows_label, 0, 0)
        recipe_stats_layout.addWidget(self.recipe_rows_value, 0, 1)

        # 刻蚀时间显示
        etch_time_label = QLabel("刻蚀时间:")
        self.etch_time_value = QLabel("--")
        self.etch_time_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.etch_time_value.setStyleSheet("""
            font-weight: bold;
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 3px;
            padding: 2px 8px;
        """)
        recipe_stats_layout.addWidget(etch_time_label, 1, 0)
        recipe_stats_layout.addWidget(self.etch_time_value, 1, 1)

        # 初始化Recipe分析器
        from core.recipe_analyzer import RecipeAnalyzer
        self.recipe_analyzer = RecipeAnalyzer()

        # 初始化模拟日志记录器
        self.simulation_logger = SimulationLogger()

        recipe_stats_group.setLayout(recipe_stats_layout)
        btn_layout.addWidget(recipe_stats_group)

        btn_layout.addWidget(self.generate_stage_speed_btn)  # 添加新按钮
        btn_layout.addSpacing(15)

        # 添加批量处理按钮
        self.batch_process_btn = QPushButton("以当前设置参数及Beam强度进行批量处理")
        self.batch_process_btn.setMinimumHeight(42)
        self.batch_process_btn.setStyleSheet("""
            QPushButton {
                background-color: #9c27b0;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #ab47bc;
            }
            QPushButton:pressed {
                background-color: #6a1b9a;
            }
            QPushButton:disabled {
                background-color: #ce93d8;
            }
        """)
        self.batch_process_btn.clicked.connect(self.start_batch_processing)
        btn_layout.addWidget(self.batch_process_btn)
        btn_layout.addSpacing(15)

        left_layout.addLayout(btn_layout)
        
        # 将左侧面板添加到分隔条
        left_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.splitter.addWidget(left_panel)
        
        # === 右侧可视化区域 (可滚动) ===
        self.visualization_container = QWidget()
        self.visualization_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 创建主布局
        main_visual_layout = QVBoxLayout(self.visualization_container)
        main_visual_layout.setContentsMargins(2, 2, 2, 2)
        main_visual_layout.setSpacing(5)
        
        # 添加选项卡控制器
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        main_visual_layout.addWidget(self.tab_widget)
        
        # === 选项卡1: 膜厚分布 ===
        thickness_tab = QWidget()
        thickness_layout = QGridLayout(thickness_tab)
        thickness_layout.setSpacing(8)
        thickness_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建4个图表容器
        self.canvas_containers_thickness = []
        for i in range(4):
            container = QWidget()
            container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(2, 2, 2, 2)
            container_layout.setSpacing(0)
            self.canvas_containers_thickness.append(container)

            # 创建画布并添加到容器
            canvas = FigureCanvas(Figure())
            canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            container_layout.addWidget(canvas)

            # 添加到布局 - 2x2网格布局
            thickness_layout.addWidget(container, i // 2, i % 2)
        
        # 为每个画布创建引用
        self.canvas_initial = self.canvas_containers_thickness[0].layout().itemAt(0).widget()
        self.canvas_etching_depth = self.canvas_containers_thickness[1].layout().itemAt(0).widget()
        self.canvas_result = self.canvas_containers_thickness[2].layout().itemAt(0).widget()
        self.canvas_etch_amount = self.canvas_containers_thickness[3].layout().itemAt(0).widget()

        # 设置背景色
        for canvas in [self.canvas_initial, self.canvas_etching_depth, self.canvas_result, self.canvas_etch_amount]:
            canvas.figure.set_facecolor('#f9f9f9')
        
        self.tab_widget.addTab(thickness_tab, "膜厚分布")
        
        # === 选项卡2: 束流与运动 ===
        beam_motion_tab = QWidget()
        beam_motion_layout = QGridLayout(beam_motion_tab)
        beam_motion_layout.setSpacing(8)
        beam_motion_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建3个图表容器
        self.canvas_containers_beam_motion = []
        for i in range(3):
            container = QWidget()
            container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(2, 2, 2, 2)
            container_layout.setSpacing(0)
            self.canvas_containers_beam_motion.append(container)
            
            # 创建画布并添加到容器
            canvas = FigureCanvas(Figure())
            canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            container_layout.addWidget(canvas)
            
            # 添加到布局
            if i < 2:
                beam_motion_layout.addWidget(container, 0, i)
            else:
                beam_motion_layout.addWidget(container, 1, 0, 1, 2)
        
        # 为每个画布创建引用
        self.canvas_beam = self.canvas_containers_beam_motion[0].layout().itemAt(0).widget()
        self.canvas_dwell = self.canvas_containers_beam_motion[1].layout().itemAt(0).widget()
        self.canvas_velocity = self.canvas_containers_beam_motion[2].layout().itemAt(0).widget()
        
        # 设置背景色
        for canvas in [self.canvas_beam, self.canvas_dwell, self.canvas_velocity]:
            canvas.figure.set_facecolor('#f9f9f9')
        
        self.tab_widget.addTab(beam_motion_tab, "束流与运动")
        
        # 初始图表
        self.init_plots()
        
        # 将分隔条添加到主布局
        self.splitter.addWidget(self.visualization_container)
        
        # 设置初始分隔比例
        self.splitter.setSizes([400, 800])
        
        # 将分隔条添加到主布局
        main_layout.addWidget(self.splitter)
    
    def init_plots(self):
        """初始化所有图表区域"""
        # === 膜厚分布选项卡 ===
        # 初始膜厚
        self.ax_initial = self.canvas_initial.figure.add_subplot(111)
        self.ax_initial.set_title("初始膜厚 (nm)", fontsize=10)
        self.ax_initial.text(0.5, 0.5, "等待模拟结果", fontsize=12,
                            ha='center', va='center', 
                            transform=self.ax_initial.transAxes,
                            color='gray', alpha=0.5)
        self.ax_initial.set_axis_off()
        self.canvas_initial.draw()
        
        # 刻蚀深度
        self.ax_etching_depth = self.canvas_etching_depth.figure.add_subplot(111)
        self.ax_etching_depth.set_title("刻蚀深度 (nm)", fontsize=10)
        self.ax_etching_depth.text(0.5, 0.5, "等待模拟结果", fontsize=12,
                            ha='center', va='center', 
                            transform=self.ax_etching_depth.transAxes,
                            color='gray', alpha=0.5)
        self.ax_etching_depth.set_axis_off()
        self.canvas_etching_depth.draw()
        
        # 刻蚀后膜厚
        self.ax_result = self.canvas_result.figure.add_subplot(111)
        self.ax_result.set_title("刻蚀后膜厚 (nm)", fontsize=10)
        self.ax_result.text(0.5, 0.5, "等待模拟结果", fontsize=12,
                            ha='center', va='center',
                            transform=self.ax_result.transAxes,
                            color='gray', alpha=0.5)
        self.ax_result.set_axis_off()
        self.canvas_result.draw()

        # 刻蚀量膜厚
        self.ax_etch_amount = self.canvas_etch_amount.figure.add_subplot(111)
        self.ax_etch_amount.set_title("刻蚀量膜厚 (nm)", fontsize=10)
        self.ax_etch_amount.text(0.5, 0.5, "等待模拟结果", fontsize=12,
                                 ha='center', va='center',
                                 transform=self.ax_etch_amount.transAxes,
                                 color='gray', alpha=0.5)
        self.ax_etch_amount.set_axis_off()
        self.canvas_etch_amount.draw()

        # === 束流与运动选项卡 ===
        # 离子束分布
        self.ax_beam = self.canvas_beam.figure.add_subplot(111)
        self.ax_beam.set_title("离子束分布", fontsize=10)
        self.ax_beam.text(0.5, 0.5, "等待模拟结果", fontsize=12,
                         ha='center', va='center', 
                         transform=self.ax_beam.transAxes,
                         color='gray', alpha=0.5)
        self.ax_beam.set_axis_off()
        self.canvas_beam.draw()
        
        # 停留时间分布
        self.ax_dwell = self.canvas_dwell.figure.add_subplot(111)
        self.ax_dwell.set_title("停留时间分布 (s)", fontsize=10)
        self.ax_dwell.text(0.5, 0.5, "等待模拟结果", fontsize=12,
                          ha='center', va='center', 
                          transform=self.ax_dwell.transAxes,
                          color='gray', alpha=0.5)
        self.ax_dwell.set_axis_off()
        self.canvas_dwell.draw()
        
        # 速度分布
        self.ax_velocity = self.canvas_velocity.figure.add_subplot(111)
        self.ax_velocity.set_title("速度分布 (mm/s)", fontsize=10)
        self.ax_velocity.text(0.5, 0.5, "等待模拟结果", fontsize=12,
                             ha='center', va='center', 
                             transform=self.ax_velocity.transAxes,
                             color='gray', alpha=0.5)
        self.ax_velocity.set_axis_off()
        self.canvas_velocity.draw()
    
    def update_stat_labels(self, initial_stats=None, target=None, validated_stats=None, etch_stats=None):
        """更新统计信息标签"""
        # 初始膜厚
        if initial_stats:
            self.stat_labels['min_initial'].setText(f"{initial_stats['min']:.1f}")
            self.stat_labels['max_initial'].setText(f"{initial_stats['max']:.1f}")
            self.stat_labels['mean_initial'].setText(f"{initial_stats['mean']:.1f}")
            self.stat_labels['range_initial'].setText(f"{initial_stats['range']:.1f}")
            self.stat_labels['uniformity_initial'].setText(f"{initial_stats.get('uniformity', 0):.2f}%")
        
        # 目标膜厚
        if target is not None:
            self.stat_labels['min_target'].setText(f"{target:.1f}")
            self.stat_labels['max_target'].setText(f"{target:.1f}")
            self.stat_labels['mean_target'].setText(f"{target:.1f}")
            self.stat_labels['range_target'].setText("0.0")
            self.stat_labels['uniformity_target'].setText("0.00%")
            
            # 设置为绿色表示成功
            for key, widget in self.stat_labels.items():
                if 'target' in key:
                    widget.setStyleSheet(widget.styleSheet() + 
                                       "; color: #006400;")  # 深绿色
        
        # 刻蚀后膜厚
        if validated_stats:
            self.stat_labels['min_result'].setText(f"{validated_stats['min']:.1f}")
            self.stat_labels['max_result'].setText(f"{validated_stats['max']:.1f}")
            self.stat_labels['mean_result'].setText(f"{validated_stats['mean']:.1f}")
            self.stat_labels['range_result'].setText(f"{validated_stats['range']:.1f}")
            self.stat_labels['uniformity_result'].setText(f"{validated_stats.get('uniformity', 0):.2f}%")
            
            # 根据均一性设置颜色
            if 'uniformity' in validated_stats:
                uniformity = validated_stats['uniformity']
                color = "#8b0000" if uniformity > 1.0 else "#006400"  # 红色表示未达标
                self.stat_labels['uniformity_result'].setStyleSheet(
                    f"font-weight: bold; background-color: #f8f8f8; border: 1px solid #e0e0e0; color: {color};"
                )

        # 刻蚀量统计
        if etch_stats:
            self.stat_labels['min_etch'].setText(f"{etch_stats['min']:.1f}")
            self.stat_labels['max_etch'].setText(f"{etch_stats['max']:.1f}")
            self.stat_labels['mean_etch'].setText(f"{etch_stats['mean']:.1f}")
            self.stat_labels['range_etch'].setText(f"{etch_stats['range']:.1f}")
            self.stat_labels['uniformity_etch'].setText(f"{etch_stats.get('uniformity', 0):.2f}%")

            # 根据刻蚀量均一性设置颜色
            if 'uniformity' in etch_stats:
                uniformity = etch_stats['uniformity']
                color = "#8b0000" if uniformity > 1.0 else "#006400"  # 红色表示未达标
                self.stat_labels['uniformity_etch'].setStyleSheet(
                    f"font-weight: bold; background-color: #f8f8f8; border: 1px solid #e0e0e0; color: {color};"
                )

        # 初始化模拟过程统计显示
        self.update_process_statistics()

    def select_etching_data(self):
        """选择初始膜厚数据文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择初始膜厚数据文件", "", "CSV文件 (*.csv);;所有文件 (*.*)"
        )
        if file_path:
            self.etching_file = file_path
            self.etching_label.setText(os.path.basename(file_path))
            self.etching_label.setStyleSheet("""
                QLabel {
                    color: #1e88e5; 
                    font-weight: bold;
                    background-color: #e1f5fe;
                    border-radius: 3px;
                    padding: 3px;
                }
            """)
            
            # 当新文件加载时，重置部分状态
            for key in ['min_result', 'max_result', 'mean_result',
                       'range_result', 'uniformity_result',
                       'min_etch', 'max_etch', 'mean_etch',
                       'range_etch', 'uniformity_etch']:
                self.stat_labels[key].setText('--')
                if 'uniformity' in key:
                    self.stat_labels[key].setStyleSheet('')
    
    def select_beam_profile(self):
        """选择离子束轮廓文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择离子束轮廓文件", "", "CSV文件 (*.csv);;所有文件 (*.*)"
        )
        if file_path:
            self.beam_file = file_path
            self.beam_label.setText(os.path.basename(file_path))
            self.beam_label.setStyleSheet("""
                QLabel {
                    color: #1e88e5; 
                    font-weight: bold;
                    background-color: #e1f5fe;
                    border-radius: 3px;
                    padding: 3px;
                }
            """)
    
    def select_output_dir(self):
        """选择输出目录"""
        output_dir = QFileDialog.getExistingDirectory(
            self, "选择输出目录", "", QFileDialog.ShowDirsOnly
        )
        if output_dir:
            self.output_dir = output_dir
            self.output_label.setText(output_dir)
            self.output_label.setStyleSheet("""
                QLabel {
                    color: #1e88e5; 
                    font-weight: bold;
                    background-color: #e1f5fe;
                    border-radius: 3px;
                    padding: 3px;
                }
            """)
    
    def run_simulation(self):
        """执行刻蚀模拟"""
        if not self.etching_file:
            QMessageBox.warning(self, "缺少文件", "请选择初始膜厚数据文件")
            return
            
        if not self.beam_file:
            QMessageBox.warning(self, "缺少文件", "请选择离子束分布文件")
            return
            
        if not self.output_dir:
            QMessageBox.warning(self, "缺少输出目录", "请选择输出目录")
            return

        # 重置模拟过程统计（新模拟开始前）
        # 如果之前有统计数据，询问用户是否确认重置
        if self.simulation_count > 1 or self.outlier_removal_count > 0:
            reply = QMessageBox.question(
                self,
                "重置统计数据",
                f"检测到之前的模拟统计数据：\n"
                f"- 模拟次数: {self.simulation_count}\n"
                f"- 异常值剔除次数: {self.outlier_removal_count}\n"
                f"- 已剔除异常点个数: {self.total_removed_points}\n\n"
                f"是否重置统计数据开始新的模拟？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.No:
                return  # 用户取消，不开始模拟

        self.reset_process_statistics()

        # 检测是否存在历史异常值文件
        if not self._check_and_handle_historical_files():
            return  # 用户选择删除历史文件，需要重新选择文件或取消

        try:
            # 初始化处理器
            grid_size = float(self.grid_size_combo.currentText())
            resolution = float(self.resolution_combo.currentText())
            wafer_diameter = float(self.wafer_diameter_combo.currentText())
            target_thickness = self.target_thickness_input.value()
            
            self.processor = IonBeamProcessor(
                grid_size=grid_size,
                resolution=resolution,
                wafer_diameter=wafer_diameter,
                transition_width=self.transition_width  # 传递用户配置的过渡区宽度
            )
            
            # 设置目标膜厚
            self.processor.set_target_thickness(target_thickness)
            
            # 更新状态
            self.main_window.update_status_message("开始刻蚀模拟...")
            
            # 禁用按钮
            self.process_btn.setEnabled(False)
            self.process_btn.setText("处理中...")
            
            # 运行模拟（新线程避免UI冻结）
            self.simulation_thread = SimulationThread(
                self.processor,
                self.etching_file,
                self.beam_file,
                self.output_dir
            )
            self.simulation_thread.results_ready.connect(self.on_simulation_complete)
            self.simulation_thread.error_occurred.connect(self.on_simulation_error)
            self.simulation_thread.start()
            
        except Exception as e:
            self.on_simulation_error(str(e))
    
    def on_simulation_complete(self, results):
        """模拟完成处理"""
        try:
            if results:
                self.main_window.update_status_message("刻蚀模拟完成!")
                # 更新图表面板
                self.update_plots()

                # 更新统计信息
                initial_stats = results.get('initial_thickness_stats', {})
                target_thickness = results.get('target_thickness', 0)
                validated_stats = results.get('validated_thickness_stats', {})  # 修改: 使用验算统计

                # 计算刻蚀量统计
                etch_stats = self.processor.calculate_etch_amount_stats()

                self.update_stat_labels(initial_stats, target_thickness, validated_stats, etch_stats)  # 修改

                # 显示完成消息或启动异常值处理
                unity_msg = ""
                if 'uniformity' in validated_stats:
                    unity = validated_stats['uniformity']
                    icon = "✅" if unity <= self.uniformity_threshold else "❌"
                    unity_msg = f"\n\n验算均一性: {unity:.2f}% {icon} (阈值: {self.uniformity_threshold:.2f}%)"

                # 根据是否为批量处理选择不同的处理流程
                if self.is_batch_processing:
                    # 批量处理流程
                    if unity <= self.uniformity_threshold:
                        # 均一性达标，直接完成单片批量处理
                        self.complete_single_batch_simulation()
                    else:
                        # 均一性不达标，启动异常值处理
                        self.outlier_processor.uniformity_threshold = self.uniformity_threshold
                        self.outlier_processor.set_simulation_callback(self.restart_batch_simulation_with_optimized_data)
                        results['original_etching_file'] = self.etching_file
                        self.outlier_processor.handle_simulation_completed(results, unity_msg, validated_stats)
                else:
                    # 单次模拟流程
                    # 更新异常值处理器的阈值（可能已在高级选项中更改）
                    self.outlier_processor.uniformity_threshold = self.uniformity_threshold
                    # 设置回调函数供异常值处理器调用
                    self.outlier_processor.set_simulation_callback(self.restart_simulation_with_optimized_data)
                    # 将原始文件路径添加到结果中
                    results['original_etching_file'] = self.etching_file
                    # 处理模拟完成，可能启动异常值优化
                    self.outlier_processor.handle_simulation_completed(results, unity_msg, validated_stats)
            else:
                self.main_window.update_status_message("刻蚀模拟失败", "error")
                QMessageBox.critical(self, "错误", "刻蚀模拟过程中发生错误")

            # 只有在非批量处理时才恢复按钮状态
            if not self.is_batch_processing:
                self.process_btn.setEnabled(True)
                self.process_btn.setText("开始模拟")

        except Exception as e:
            if self.is_batch_processing:
                self.on_batch_simulation_error(str(e))
            else:
                self.on_simulation_error(str(e))
    
    def on_simulation_error(self, error_message):
        """模拟错误处理"""
        self.main_window.update_status_message(f"模拟错误: {error_message}", "error")
        QMessageBox.critical(self, "错误", f"刻蚀模拟过程中发生错误:\n{error_message}")
        self.process_btn.setEnabled(True)
        self.process_btn.setText("开始模拟")

    def restart_simulation_with_optimized_data(self, new_file_path, new_data):
        """使用优化后的数据重新启动模拟"""
        try:
            # 更新状态消息
            self.main_window.update_status_message(f"使用优化数据 {os.path.basename(new_file_path)} 开始重新模拟...")

            # 增加模拟次数
            self.increment_simulation_count()

            # 创建新的工作线程，使用相同的4参数构造函数
            # 需要传递原始文件路径。在单片模式下，self.etching_file应该就是原始文件
            original_file = getattr(self, 'etching_file', new_file_path)
            print(f"[DEBUG] restart_simulation_with_optimized_data: new_file_path={new_file_path}, original_file={original_file}")
            self.simulation_thread = CustomSimulationThread(
                self.processor,
                new_file_path,
                self.beam_file,
                self.output_dir,
                original_file  # 单片模式下的原始文件
            )

            # 连接信号
            self.simulation_thread.results_ready.connect(self.on_optimized_simulation_completed)
            self.simulation_thread.error_occurred.connect(self.on_simulation_error)

            # 启动线程
            self.simulation_thread.start()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"重新启动模拟失败: {str(e)}")
            self.process_btn.setEnabled(True)
            self.process_btn.setText("开始模拟")

    def on_optimized_simulation_completed(self, results):
        """优化数据模拟完成处理"""
        try:
            # 更新图表
            self.update_plots()

            # 更新统计信息（使用与原始模拟相同的方式）
            initial_stats = results.get('initial_thickness_stats', {})
            target_thickness = results.get('target_thickness', 0)
            validated_stats = results.get('validated_thickness_stats', {})  # 使用验算统计

            # 计算刻蚀量统计
            etch_stats = self.processor.calculate_etch_amount_stats()

            self.update_stat_labels(initial_stats, target_thickness, validated_stats, etch_stats)

            # 检查均一性是否达标
            unity_msg = ""
            if 'uniformity' in validated_stats:
                unity = validated_stats['uniformity']
                icon = "✅" if unity <= self.uniformity_threshold else "❌"
                unity_msg = f"\n\n验算均一性: {unity:.2f}% {icon} (阈值: {self.uniformity_threshold:.2f}%)"

                # 如果仍不达标，继续处理
                if unity > self.uniformity_threshold:
                    if self.is_batch_processing:
                        self.outlier_processor.handle_simulation_completed(results, unity_msg, validated_stats)
                    else:
                        self.outlier_processor.handle_simulation_completed(results, unity_msg, validated_stats)
                    return

            # 根据是否为批量处理选择不同的完成流程
            if self.is_batch_processing:
                # 批量处理：单片完成
                self.complete_single_batch_simulation()
            else:
                # 单个处理：显示完成消息
                QMessageBox.information(self, "完成",
                    f"刻蚀模拟完成!{unity_msg}\n"
                    f"- 初始膜厚图: {os.path.basename(results['initial_thickness_map'])}\n"
                    f"- 刻蚀深度图: {os.path.basename(results['etching_depth_map'])}\n"
                    f"- 验算膜厚图: {os.path.basename(results['validated_thickness_map'])}\n"
                    f"- 停留时间图: {os.path.basename(results['dwell_time_map'])}\n"
                    f"- 速度分布图: {os.path.basename(results['velocity_map'])}\n"
                    f"- 轨迹文件: {os.path.basename(results['stage_recipe'])}")

                self.process_btn.setEnabled(True)
                self.process_btn.setText("开始模拟")

        except Exception as e:
            if self.is_batch_processing:
                self.on_batch_simulation_error(str(e))
            else:
                self.on_simulation_error(str(e))

    def update_process_statistics(self):
        """更新模拟过程统计显示"""
        try:
            # 更新模拟次数
            self.process_stat_labels['simulation_count'].setText(str(self.simulation_count))

            # 更新异常值剔除次数
            self.process_stat_labels['outlier_removal_count'].setText(str(self.outlier_removal_count))

            # 更新已剔除异常点个数
            self.process_stat_labels['total_removed_points'].setText(str(self.total_removed_points))

            # 根据统计信息设置不同的颜色提示
            # 模拟次数始终显示为正常
            self.process_stat_labels['simulation_count'].setStyleSheet("""
                font-weight: bold;
                background-color: #e8f5e8;
                border: 1px solid #c3e6c3;
                border-radius: 3px;
                padding: 2px 8px;
            """)

            # 异常值剔除次数：0为正常，>0为警告状态
            if self.outlier_removal_count == 0:
                outlier_style = """
                    font-weight: bold;
                    background-color: #e8f5e8;
                    border: 1px solid #c3e6c3;
                    border-radius: 3px;
                    padding: 2px 8px;
                """
            else:
                outlier_style = """
                    font-weight: bold;
                    background-color: #fff3cd;
                    border: 1px solid #ffeaa7;
                    border-radius: 3px;
                    padding: 2px 8px;
                """
            self.process_stat_labels['outlier_removal_count'].setStyleSheet(outlier_style)

            # 已剔除异常点个数：0为正常，>0为警告状态
            if self.total_removed_points == 0:
                removed_style = """
                    font-weight: bold;
                    background-color: #e8f5e8;
                    border: 1px solid #c3e6c3;
                    border-radius: 3px;
                    padding: 2px 8px;
                """
            else:
                removed_style = """
                    font-weight: bold;
                    background-color: #f8d7da;
                    border: 1px solid #f5c6cb;
                    border-radius: 3px;
                    padding: 2px 8px;
                """
            self.process_stat_labels['total_removed_points'].setStyleSheet(removed_style)

        except Exception as e:
            print(f"更新模拟过程统计失败: {str(e)}")

    def increment_simulation_count(self):
        """增加模拟次数"""
        self.simulation_count += 1
        self.update_process_statistics()

    def increment_outlier_removal_count(self, removed_points=0):
        """增加异常值剔除次数和剔除点数"""
        self.outlier_removal_count += 1
        self.total_removed_points += removed_points
        self.update_process_statistics()

    def increment_min_value_removal_count(self, removed_points=0):
        """增加最小值剔除次数和剔除点数"""
        if not hasattr(self, 'min_value_removal_count'):
            self.min_value_removal_count = 0
        self.min_value_removal_count += 1
        self.total_removed_points += removed_points
        self.update_process_statistics()
        print(f"[STAT_DEBUG] 最小值剔除次数: {self.min_value_removal_count}, 已剔除最小值个数: {self.total_removed_points}")

    def set_original_data_count(self, count):
        """设置原始数据点数"""
        self.original_data_count = count
        self.update_process_statistics()

    def reset_process_statistics(self):
        """重置模拟过程统计（用于新的模拟开始）"""
        self.simulation_count = 1
        self.outlier_removal_count = 0
        self.min_value_removal_count = 0  # 同时重置最小值剔除次数
        self.total_removed_points = 0
        self.update_process_statistics()
        print(f"[STAT_DEBUG] 统计已重置: 模拟次数={self.simulation_count}, 异常值剔除次数={self.outlier_removal_count}, 最小值剔除次数={self.min_value_removal_count}")

    def _check_and_handle_historical_files(self):
        """检查并处理历史异常值文件"""
        try:
            import glob

            if not self.etching_file or not os.path.exists(self.etching_file):
                return True

            # 获取原始文件的基本名称（不含扩展名）
            base_name = os.path.splitext(os.path.basename(self.etching_file))[0]
            file_dir = os.path.dirname(self.etching_file)

            # 查找所有历史异常值文件
            patterns = [
                f"{base_name}_error_deleted_*_time.csv",
                f"{base_name}_min_removed_*.csv",
                f"{base_name}_error_deleted_*_time_min_removed_*.csv"
            ]

            historical_files = []
            for pattern in patterns:
                files = glob.glob(os.path.join(file_dir, pattern))
                historical_files.extend(files)

            if not historical_files:
                return True  # 没有历史文件，可以继续

            # 按文件名排序
            historical_files.sort()
            file_names = [os.path.basename(f) for f in historical_files]

            # 显示历史文件列表
            file_list_text = "\n".join([f"- {name}" for name in file_names])

            reply = QMessageBox.question(
                self,
                "存在模拟历史",
                f"检测到以下历史异常值文件：\n\n"
                f"{file_list_text}\n\n"
                f"这些文件可能会影响新的模拟逻辑。\n"
                f"是否删除所有历史文件并重新开始模拟？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No  # 默认选择否，更安全
            )

            if reply == QMessageBox.Yes:
                # 用户确认删除，删除所有历史文件
                deleted_files = []
                failed_files = []

                for file_path in historical_files:
                    try:
                        os.remove(file_path)
                        deleted_files.append(os.path.basename(file_path))
                    except Exception as e:
                        failed_files.append(f"{os.path.basename(file_path)}: {str(e)}")

                # 显示删除结果
                if deleted_files:
                    deleted_list = "\n".join([f"[成功] {name}" for name in deleted_files])
                    if failed_files:
                        failed_list = "\n".join([f"[失败] {name}" for name in failed_files])
                        QMessageBox.information(
                            self,
                            "删除历史文件",
                            f"成功删除的文件：\n{deleted_list}\n\n"
                            f"删除失败的文件：\n{failed_list}\n\n"
                            f"现在可以开始新的模拟。"
                        )
                    else:
                        QMessageBox.information(
                            self,
                            "删除历史文件",
                            f"成功删除以下文件：\n{deleted_list}\n\n"
                            f"现在可以开始新的模拟。"
                        )
                    return True
                else:
                    QMessageBox.warning(
                        self,
                        "删除失败",
                        f"无法删除任何历史文件。\n\n"
                        f"请手动删除以下文件后重试：\n{file_list_text}"
                    )
                    return False
            else:
                # 用户选择不删除，但仍然可以继续模拟
                # 显示警告，但允许继续
                QMessageBox.warning(
                    self,
                    "保留历史文件",
                    f"将保留历史文件继续模拟。\n\n"
                    f"注意：这可能会导致异常值处理逻辑出现混乱。\n"
                    f"建议先备份当前文件再继续。"
                )
                return True

        except Exception as e:
            print(f"检查历史文件时出错: {str(e)}")
            return True  # 出错时默认允许继续

    def update_plots(self):
        """更新所有图表显示模拟结果"""
        print(f"[DEBUG] update_plots 开始执行")
        try:
            print(f"[DEBUG] 开始更新膜厚分布图")
            # 更新膜厚分布图
            self.update_single_thickness_plot(
                self.ax_initial,
                self.processor.initial_thickness_map,
                "初始膜厚 (nm)",
                'viridis',
                True,
                self.processor
            )
            print(f"[DEBUG] 初始膜厚图更新完成")
            
            self.update_single_thickness_plot(
                self.ax_etching_depth,
                self.processor.etching_depth_map if hasattr(self.processor, 'etching_depth_map') else None,
                "目标刻蚀深度 (nm)",
                'plasma',
                True,
                self.processor
            )
            
            # 修改: 显示验算后膜厚
            self.update_single_thickness_plot(
                self.ax_result,
                self.processor.get_validated_thickness_map() if hasattr(self.processor, 'get_validated_thickness_map') else None,
                "验算后膜厚 (nm)",
                'coolwarm',
                True,
                self.processor
            )

            # 新增: 显示刻蚀量膜厚
            etch_amount_data = None
            if (hasattr(self.processor, 'initial_thickness_map') and
                hasattr(self.processor, 'get_validated_thickness_map')):
                initial_map = self.processor.initial_thickness_map
                validated_map = self.processor.get_validated_thickness_map()
                if initial_map is not None and validated_map is not None:
                    # 计算刻蚀量 = 初始膜厚 - 验算后膜厚
                    etch_amount_data = initial_map - validated_map

            self.update_single_thickness_plot(
                self.ax_etch_amount,
                etch_amount_data,
                "刻蚀量膜厚 (nm)",
                'coolwarm',  # 使用与验算后膜厚相同的颜色风格
                True,
                self.processor
            )

            # 更新束流与运动图
            if hasattr(self.processor, 'dwell_time'):
                self.update_single_plot(
                    self.ax_dwell,
                    self.processor.dwell_time, 
                    "停留时间分布 (s)",
                    'cividis',
                    True,
                    self.processor
                )
                
                # 更新离子束分布图
                self.update_single_plot(
                    self.ax_beam,
                    self.processor.beam_profile, 
                    "离子束分布",
                    'inferno',
                    True,
                    self.processor
                )
                
                # 更新速度分布图
                self.update_single_plot(
                    self.ax_velocity,
                    self.processor.velocity_map if hasattr(self.processor, 'velocity_map') else None,
                    "速度分布 (mm/s)",
                    'jet',
                    True,
                    self.processor
                )
            
            # 重绘画布
            print(f"[DEBUG] 开始重绘画布，共7个画布")
            for i, canvas in enumerate([self.canvas_initial, self.canvas_etching_depth, self.canvas_result,
                          self.canvas_etch_amount, self.canvas_beam, self.canvas_dwell, self.canvas_velocity]):
                print(f"[DEBUG] 重绘画布 {i}/6")
                try:
                    canvas.draw()
                    print(f"[DEBUG] 画布 {i} 绘制完成")
                except Exception as canvas_e:
                    print(f"[DEBUG] 画布 {i} 绘制失败: {str(canvas_e)}")
                    continue
            print(f"[DEBUG] 所有画布重绘完成")
                
        except Exception as e:
            print(f"更新图表错误: {str(e)}")
    
    def update_single_thickness_plot(self, ax, data, title, cmap, add_circle, processor):
        """更新单个膜厚分布图表 - 仅显示晶圆内部区域"""
        # 在清除坐标轴之前先移除colorbar
        if hasattr(ax, '_colorbar') and ax._colorbar is not None:
            ax._colorbar.remove()
            ax._colorbar = None
        
        ax.clear()
        grid_size = processor.grid_size

        # 创建图像
        if data is None:
            im = ax.imshow(np.zeros((10, 10)), 
                       extent=[-grid_size/2, grid_size/2, 
                               -grid_size/2, grid_size/2],
                       cmap='afmhot')
            ax.text(0.5, 0.5, "数据不可用", 
                   ha='center', va='center', 
                   transform=ax.transAxes,
                   color='red', fontsize=12)
        else:
            # 创建晶圆掩模（仅显示晶圆内部区域）
            r = np.sqrt(processor.X**2 + processor.Y**2)
            wafer_mask = r <= processor.wafer_radius
            
            # 应用掩模：只保留晶圆内部的数值，外部设为NaN（透明）
            masked_data = np.full_like(data, np.nan)
            masked_data[wafer_mask] = data[wafer_mask]
            
            # 创建图像（使用masked_array确保透明效果）
            im = ax.imshow(masked_data, 
                   extent=[-grid_size/2, grid_size/2, 
                           -grid_size/2, grid_size/2],
                   cmap=cmap, origin='lower')
            
            # 添加颜色条
            # 添加颜色条并保存到axes对象
            cbar = ax.figure.colorbar(im, ax=ax, shrink=0.8)
            ax._colorbar = cbar  # 保存到axes对象中
            cbar.set_label('nm')
        
        # 添加晶圆轮廓
        if add_circle:
            circle = plt.Circle((0, 0), processor.wafer_radius, 
                            fill=False, edgecolor='white', 
                            linestyle='--', linewidth=1.5)  # 加粗轮廓线
            ax.add_artist(circle)
        
        # 设置标题和标签
        ax.set_title(title, fontsize=10)
        ax.set_xlabel('X (mm)', fontsize=9)
        ax.set_ylabel('Y (mm)', fontsize=9)
        
        # 优化布局
        plt.tight_layout(pad=1.0)
    
    def update_single_plot(self, ax, data, title, cmap, add_circle, processor):
        """更新单个图表（为停留时间分布图添加遮罩）"""
        if data is None:
            return
        
        # 在清除坐标轴之前先移除colorbar
        if hasattr(ax, '_colorbar') and ax._colorbar is not None:
            ax._colorbar.remove()
            ax._colorbar = None
        
        ax.clear()
        grid_size = processor.grid_size
        vmin = None
        vmax = None

        # 检查是否为停留时间分布图或速度分布图（需要晶圆内部遮罩）
        if title in ["停留时间分布 (s)", "速度分布 (mm/s)"]:
            # 创建晶圆掩模（仅显示晶圆内部区域）
            r = np.sqrt(processor.X**2 + processor.Y**2)
            wafer_mask = r <= processor.wafer_radius
            
            # 应用掩模：只保留晶圆内部的数值，外部设为NaN（透明）
            masked_data = np.full_like(data, np.nan)
            masked_data[wafer_mask] = data[wafer_mask]
            
            # 自动计算颜色范围（基于晶圆内部数据）
            if np.any(~np.isnan(masked_data)):
                vmin = np.nanmin(masked_data)
                vmax = np.nanmax(masked_data)
            
            # 创建图像（使用masked_array确保透明效果）
            im = ax.imshow(masked_data, 
                        extent=[-grid_size/2, grid_size/2, 
                                -grid_size/2, grid_size/2],
                        cmap=cmap, origin='lower',
                        vmin=vmin, vmax=vmax)
        else:
            # 其他图表正常绘制
            im = ax.imshow(data, 
                        extent=[-grid_size/2, grid_size/2, 
                                -grid_size/2, grid_size/2],
                        cmap=cmap, origin='lower')
        
        # 添加晶圆轮廓
        circle = plt.Circle((0, 0), processor.wafer_radius, 
                            fill=False, edgecolor='white', 
                            linestyle='--', linewidth=1.2)
        ax.add_artist(circle)
        
        # 设置标题和标签
        ax.set_title(title, fontsize=10)
        ax.set_xlabel('X (mm)', fontsize=9)
        ax.set_ylabel('Y (mm)', fontsize=9)

        # 添加颜色条
        # 添加颜色条并保存到axes对象
        cbar = ax.figure.colorbar(im, ax=ax, shrink=0.8)
        ax._colorbar = cbar  # 保存到axes对象中
        
        # 对特定图表添加额外信息
        if title in ["停留时间分布 (s)", "速度分布 (mm/s)"] and vmin is not None and vmax is not None:
            # 设置标签单位
            unit = "s" if title == "停留时间分布 (s)" else "mm/s"
            cbar.set_label(unit)
            
            # 添加统计信息到标题
            ax.set_title(f"{title} [内部: {vmin:.4f}-{vmax:.4f} {unit.replace('(', '').replace(')', '').strip()}]", fontsize=10)
        
        # 优化布局
        plt.tight_layout(pad=1.0)

    def generate_stage_speed_map(self):
        """生成载台运动速度地图"""
        print(f"[DEBUG] generate_stage_speed_map 开始执行")
        # 检查输出目录是否设置
        if not self.output_dir:
            print(f"[DEBUG] 错误：未设置输出目录")
            QMessageBox.warning(self, "错误", "请先选择输出目录")
            return

        # 检查是否已经生成了速度文件
        velocity_file = os.path.join(self.output_dir, "velocity_map.csv")
        print(f"[DEBUG] 检查速度文件: {velocity_file}")
        if not os.path.exists(velocity_file):
            print(f"[DEBUG] 错误：速度文件不存在")
            QMessageBox.warning(self, "错误", "速度分布文件不存在，请先运行模拟")
            return

        print(f"[DEBUG] 速度文件存在，开始读取")
        try:
            print(f"[DEBUG] 开始处理速度地图数据")
            # 获取载台中心点坐标
            x_center = self.stage_center_x.value()
            y_center = self.stage_center_y.value()
            print(f"[DEBUG] 载台中心: X={x_center}, Y={y_center}")

            # 获取y步长设置
            y_step = int(self.y_step_combo.currentText())
            print(f"[DEBUG] Y步长: {y_step}")

            # 读取速度分布文件
            print(f"[DEBUG] 开始读取CSV文件")
            df = pd.read_csv(velocity_file)
            print(f"[DEBUG] CSV文件读取完成，尺寸: {df.shape}")
            
            # 获取Y坐标列名（通常是第一列）
            y_col = df.columns[0]
            
            original_y_coords = df[y_col].values
            
            # 1. 创建新的DataFrame（保持速度值不变）
            new_df = df.copy()
            new_df[y_col] = original_y_coords
            
            # 获取网格尺寸（从X坐标范围推断）
            x_cols = list(new_df.columns[1:])  # X坐标列名
            x_coords = np.array([float(x) for x in x_cols])
            
            # 计算原始尺寸（假设为正方形）
            grid_size = (max(x_coords) - min(x_coords)) + (x_coords[1]-x_coords[0])
            
            # 2. 坐标平移（到载台中心）
            new_df[y_col] += y_center
            new_x_cols = [str(float(x) + x_center) for x in x_cols]
            new_df.rename(columns=dict(zip(x_cols, new_x_cols)), inplace=True)
            
            # 3. 确定截取范围（使用用户配置的Recipe截取范围）
            half_size = self.recipe_range / 2
            min_x = x_center - half_size
            max_x = x_center + half_size
            min_y = y_center - half_size
            max_y = y_center + half_size
            
            # 4.1 首先按Y坐标截取
            y_values = new_df[y_col].values
            y_mask = (y_values >= min_y) & (y_values <= max_y)
            cropped_df = new_df[y_mask]
            
            # 4.2 然后按X坐标截取
            x_cols_to_keep = [col for col in cropped_df.columns[1:] 
                            if min_x <= float(col) <= max_x]
            
            # 创建最终DataFrame (包含Y列和选择的X列)
            final_df = cropped_df.loc[:, [y_col] + x_cols_to_keep].copy()

            #################################################
            # 关键修改：仅反转Y列的值，同时保留行顺序
            #################################################
            
            # 获取Y值列
            y_values = final_df[y_col].values
            
            # 反转Y值数组但保持行顺序
            reversed_y = np.flip(y_values)
            
            # 只替换Y列，保持其他列不变
            final_df.loc[:, y_col] = reversed_y
            
            #################################################

            #################################################
            # 修正的y-Step步长处理逻辑
            #################################################
            # 获取总行数（包括标题行）
            total_rows = len(final_df)
            
            if y_step > 1:
                # 记录原始信息
                original_count = total_rows
                
                # 计算应该保留的行（标题行和每隔y_step选取的数据行）
                rows_to_keep = []
                #rows_to_keep.append(0)  # 总是保留标题行
                
                # 从第二行（索引0）开始，每隔(y_step)行选取一行
                current_index = 0
                while current_index < total_rows:
                    rows_to_keep.append(current_index)
                    current_index += y_step
                    
                # 选择保留的这些行
                final_df = final_df.iloc[rows_to_keep]
                
                # 重置索引，使其连续
                final_df.reset_index(drop=True, inplace=True)
                
                # 记录变化情况
                new_count = len(final_df)
                reduction = original_count - new_count
                reduction_pct = (reduction / original_count) * 100 if original_count > 0 else 0
            #################################################
            
            # 保存文件
            output_path = os.path.join(self.output_dir, "stage_Y-motor_speed_map.csv")
            final_df.to_csv(output_path, index=False)
            
            # 创建报告信息
            info_msg = f"载台运动速度文件已生成!\n文件名: {os.path.basename(output_path)}\n"
            info_msg += f"尺寸: {len(final_df)}行 x {len(final_df.columns)-1}列\n"
            
            if y_step > 1:
                info_msg += (
                    f"y-Step步长: {y_step}\n"
                    f"原始行数: {original_count}, 保留行数: {new_count}\n"
                    f"减少行数: {reduction} ({reduction_pct:.1f}%)\n"
                )
            
            # 添加Y坐标范围信息
            if len(final_df) > 1:
                # 获取标题行后的第一个Y值（最大Y值）
                first_value = final_df.iloc[0][y_col]
                # 获取最后一行（最小Y值）
                last_value = final_df.iloc[-1][y_col]
                info_msg += f"Y坐标范围: {first_value:.2f}mm 到 {last_value:.2f}mm" 
                
                # 添加实际步长信息（如果有多于2个数据点）
                if len(final_df) > 2:
                    try:
                        # 获取标题行后的Y值（第1行到最后一行）
                        y_values = final_df[y_col].iloc[1:].values
                        # 计算连续点之间的差（取绝对值）
                        differences = np.abs(np.diff(y_values))
                        # 报告第一个步长值
                        actual_step = differences[0]
                        info_msg += f", 实际y步长: {actual_step:.2f}mm"
                    except Exception as e:
                        self.main_window.log(f"计算实际步长出错: {str(e)}")

            # 新增：生成SMI Recipe文件 - 使用新规则命名
            print(f"[DEBUG] 开始生成SMI Recipe文件名")
            smi_filename = self.generate_smi_filename()
            smi_recipe_path = os.path.join(self.output_dir, smi_filename)
            print(f"[DEBUG] SMI Recipe文件: {smi_recipe_path}")

            print(f"[DEBUG] 开始调用generate_smi_recipe")
            self.generate_smi_recipe(final_df, smi_recipe_path)
            print(f"[DEBUG] generate_smi_recipe调用完成")

            info_msg += f"\n\nSMI指令文件已生成!\n文件名: {smi_filename}\n"
            info_msg += f"尺寸: {self.recipe_rows}行 X 5列\n"
            info_msg += f"Recipe截取范围: {self.recipe_range}mm"

            # 根据刻蚀量平均值生成倍速Recipe
            speed_recipes = self._generate_speed_recipes(smi_recipe_path, smi_filename)
            if speed_recipes:
                info_msg += f"\n\n倍速Recipe已生成!"
                for recipe_info in speed_recipes:
                    info_msg += f"\n- {recipe_info['description']}: {recipe_info['filename']}"

            # 生成模拟日志
            try:
                simulation_log_path = self._generate_simulation_log()
                if simulation_log_path:
                    log_filename = os.path.basename(simulation_log_path)
                    info_msg += f"\n\n模拟日志已生成!\n文件名: {log_filename}"
            except Exception as log_e:
                self.main_window.log(f"生成模拟日志失败: {str(log_e)}")

            QMessageBox.information(self, "成功", info_msg)

            self.main_window.update_status_message(f"生成载台运动速度地图 (y-step={y_step}): {output_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"生成载台运动速度失败:\n{str(e)}")
            self.main_window.update_status_message(f"生成载台运动速度失败: {str(e)}", "error")

    # 新增的函数
    def generate_smi_recipe(self, speed_map_df, output_path):
        """根据速度地图生成SMI Recipe文件

        Args:
            speed_map_df: 载台速度地图DataFrame
            output_path: 输出文件路径
        """
        print(f"[DEBUG] generate_smi_recipe 开始执行")
        print(f"[DEBUG] 输入DataFrame尺寸: {speed_map_df.shape}")
        print(f"[DEBUG] 输出路径: {output_path}")

        # 获取列名和行索引信息
        y_col = speed_map_df.columns[0]  # Y坐标列名
        x_columns = list(speed_map_df.columns[1:])  # X坐标列名列表
        print(f"[DEBUG] Y列名: {y_col}, X列数: {len(x_columns)}")
        
        # 创建列名到X坐标的映射（字符串到浮点数）
        x_positions = {}
        for col_name in x_columns:
            try:
                x_positions[col_name] = float(col_name)
            except ValueError:
                # 如果无法转换为浮点数，保留原始值
                x_positions[col_name] = col_name
        
        # 准备SMI Recipe数据
        recipe_data = []
        self.recipe_rows = 0  # 记录生成的行数
        
        # 跟踪上一个点的X位置
        prev_x = None
        
        # 蛇形遍历所有列
        total_columns = len(x_columns)
        print(f"[DEBUG] 开始蛇形遍历 {total_columns} 列")

        for col_idx, col_name in enumerate(x_columns):
            if col_idx % 10 == 0:  # 每处理10列输出一次进度
                print(f"[DEBUG] 处理第 {col_idx+1}/{total_columns} 列: {col_name}")

            # 确定列遍历方向（奇数列向上，偶数列向下）
            col_data = speed_map_df[[y_col, col_name]]

            if col_idx % 2 == 1:  # 奇数列，从下往上遍历
                col_data = col_data.iloc[::-1].reset_index(drop=True)

            # 遍历该列的所有行
            for row_idx, row in col_data.iterrows():
                # 第一行是坐标标题行，跳过
                if row_idx == 0:
                    continue
                    
                point_number = self.recipe_rows + 1
                y_pos = float(row[y_col])  # Y位置
                x_pos = x_positions[col_name]  # X位置
                y_speed = float(row[col_name])  # Y速度
                
                # 确定X速度 (与前一行的X位置比较)
                if self.recipe_rows == 0:
                    # 第一点默认100
                    x_speed = 100.0
                else:
                    # 比较当前X位置和前一个点的X位置
                    x_speed = 100.0 if x_pos != prev_x else 0.0
                
                # 添加到recipe数据
                recipe_data.append({
                    "Point": point_number,
                    "X-Position": x_pos,
                    "X-Speed": x_speed,
                    "Y-Position": y_pos,
                    "Y-Speed": y_speed
                })
                
                self.recipe_rows += 1
                prev_x = x_pos
        
        # 规则8: 对于X-Speed为100的行(除了第一行)，设置Y-Speed为0
        for i in range(1, len(recipe_data)):  # 从第二行开始(索引1)
            if recipe_data[i]["X-Speed"] == 100.0:
                recipe_data[i]["Y-Speed"] = 0.0
        
        # 规则9: 添加最后一行全0的数据
        # 下一行的Point编号
        last_point = recipe_data[-1]["Point"] + 1 if recipe_data else 1
        recipe_data.append({
            "Point": last_point,
            "X-Position": 0.0,
            "X-Speed": 0.0,
            "Y-Position": 0.0,
            "Y-Speed": 0.0
        })
        self.recipe_rows += 1  # 增加行数计数

        print(f"[DEBUG] 蛇形遍历完成，共生成 {self.recipe_rows} 行数据")

        # 规则8: 对于X-Speed为100的行(除了第一行)，设置Y-Speed为0
        print(f"[DEBUG] 开始应用规则8")
        for i in range(1, len(recipe_data)):  # 从第二行开始(索引1)
            if recipe_data[i]["X-Speed"] == 100.0:
                recipe_data[i]["Y-Speed"] = 0.0

        # 规则9: 添加最后一行全0的数据
        # 下一行的Point编号
        last_point = recipe_data[-1]["Point"] + 1 if recipe_data else 1
        recipe_data.append({
            "Point": last_point,
            "X-Position": 0.0,
            "X-Speed": 0.0,
            "Y-Position": 0.0,
            "Y-Speed": 0.0
        })
        self.recipe_rows += 1  # 增加行数计数
        print(f"[DEBUG] 添加最后一行，总行数: {self.recipe_rows}")

        # 创建DataFrame并保存
        print(f"[DEBUG] 开始创建DataFrame并保存CSV")
        if recipe_data:
            recipe_df = pd.DataFrame(recipe_data)
            print(f"[DEBUG] DataFrame创建完成，开始保存到: {output_path}")
            recipe_df.to_csv(output_path, index=False)
            print(f"[DEBUG] CSV文件保存完成")

            # 更新Recipe统计信息
            print(f"[DEBUG] 开始更新Recipe统计信息")
            self._update_recipe_statistics(output_path)
            print(f"[DEBUG] Recipe统计信息更新完成")
        else:
            print(f"[DEBUG] 错误：没有生成任何SMI Recipe行")
            raise ValueError("没有生成任何SMI Recipe行，可能的原因：输入文件为空")

        print(f"[DEBUG] generate_smi_recipe 执行完成")
        
    # 新增的方法
    def generate_smi_filename(self):
        """根据当前选择的刻蚀文件和束流文件生成SMI Recipe文件名"""
        # 获取刻蚀文件名（不带扩展名）
        etching_name = ""
        if self.etching_file:
            etching_filename = os.path.basename(self.etching_file)
            etching_name, _ = os.path.splitext(etching_filename)
            etching_name = etching_name.replace(" ", "_").replace("(", "").replace(")", "")
        
        # 获取离子束文件名（不带扩展名）
        beam_name = ""
        if self.beam_file:
            beam_filename = os.path.basename(self.beam_file)
            beam_name, _ = os.path.splitext(beam_filename)
            beam_name = beam_name.replace(" ", "_").replace("(", "").replace(")", "")
        
        # 构建组合文件名
        if etching_name and beam_name:
            return f"{etching_name}_{beam_name}_Stage_Movement_Instruction_Recipe.csv"
        elif etching_name:
            return f"{etching_name}_Stage_Movement_Instruction_Recipe.csv"
        elif beam_name:
            return f"{beam_name}_Stage_Movement_Instruction_Recipe.csv"
        else:
            return "Stage_Movement_Instruction_Recipe.csv"

    def show_advanced_options(self):
        """显示高级选项设置对话框"""
        dialog = AdvancedOptionsDialog(self.transition_width, self.recipe_range, self.uniformity_threshold, self.speed_threshold, self)
        if dialog.exec_() == QMessageBox.Accepted:
            # 获取用户设置的新值
            self.transition_width = dialog.get_transition_width()
            self.recipe_range = dialog.get_recipe_range()
            self.uniformity_threshold = dialog.get_uniformity_threshold()
            self.speed_threshold = dialog.get_speed_threshold()

            # 保存到配置文件
            try:
                config_manager = get_config_manager()
                config_manager.set_transition_width(self.transition_width)
                config_manager.set_recipe_range(self.recipe_range)
                config_manager.set_uniformity_threshold(self.uniformity_threshold)
                config_manager.set_speed_threshold(self.speed_threshold)

                self.main_window.update_status_message(
                    f"高级选项已更新并保存: 过渡区宽度={self.transition_width}mm, Recipe截取范围={self.recipe_range}mm, 均一性阈值={self.uniformity_threshold}%, 刻蚀量阈值={self.speed_threshold}nm"
                )
            except Exception as e:
                self.main_window.update_status_message(f"保存高级选项失败: {str(e)}", "error")

    def _update_recipe_statistics(self, recipe_file_path):
        """更新Recipe统计信息显示

        Args:
            recipe_file_path: Recipe文件路径
        """
        print(f"[DEBUG] _update_recipe_statistics 开始执行")
        print(f"[DEBUG] Recipe文件路径: {recipe_file_path}")
        try:
            if hasattr(self, 'recipe_analyzer') and os.path.exists(recipe_file_path):
                print(f"[DEBUG] 开始分析Recipe文件")
                recipe_rows, etch_time_formatted, etch_time_seconds = self.recipe_analyzer.analyze_recipe_file(recipe_file_path)
                print(f"[DEBUG] Recipe分析完成: 行数={recipe_rows}, 时间={etch_time_formatted}")

                # 更新UI显示
                self.recipe_rows_value.setText(str(recipe_rows))
                self.etch_time_value.setText(etch_time_formatted)
                print(f"[DEBUG] UI显示更新完成")

                # 为刻蚀时间应用不同的背景色（类似总剔除点数的红色系）
                self.etch_time_value.setStyleSheet("""
                    font-weight: bold;
                    background-color: #f8d7da;
                    border: 1px solid #f5c6cb;
                    border-radius: 3px;
                    padding: 2px 8px;
                """)

                # 记录到状态栏
                self.main_window.update_status_message(
                    f"Recipe统计已更新: 行数={recipe_rows}, 刻蚀时间={etch_time_formatted}"
                )
            else:
                # 重置显示
                self.recipe_rows_value.setText("--")
                self.etch_time_value.setText("--")
                # 恢复默认样式
                self.recipe_rows_value.setStyleSheet("""
                    font-weight: bold;
                    background-color: #e8f5e8;
                    border: 1px solid #c3e6c3;
                    border-radius: 3px;
                    padding: 2px 8px;
                """)
                self.etch_time_value.setStyleSheet("""
                    font-weight: bold;
                    background-color: #fff3cd;
                    border: 1px solid #ffeaa7;
                    border-radius: 3px;
                    padding: 2px 8px;
                """)

        except Exception as e:
            print(f"更新Recipe统计失败: {str(e)}")
            # 显示错误状态 - 使用红色背景表示错误
            error_style = """
                font-weight: bold;
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
                border-radius: 3px;
                padding: 2px 8px;
                color: #721c24;
            """
            self.recipe_rows_value.setText("错误")
            self.recipe_rows_value.setStyleSheet(error_style)
            self.etch_time_value.setText("错误")
            self.etch_time_value.setStyleSheet(error_style)

    def _save_stage_center_config(self):
        """保存载台中心坐标到配置文件"""
        try:
            config_manager = get_config_manager()
            x_value = self.stage_center_x.value()
            y_value = self.stage_center_y.value()

            if config_manager.set_stage_center(x_value, y_value):
                print(f"载台中心坐标已保存: X={x_value}, Y={y_value}")
            else:
                print("载台中心坐标保存失败")

        except Exception as e:
            print(f"保存载台中心坐标时出错: {str(e)}")

    def _generate_speed_recipes(self, original_recipe_path, original_filename):
        """
        根据刻蚀量平均值生成倍速Recipe文件

        Args:
            original_recipe_path: 原始Recipe文件路径
            original_filename: 原始Recipe文件名

        Returns:
            list: 生成的倍速Recipe信息列表
        """
        speed_recipes = []

        try:
            # 获取刻蚀量平均值
            etching_amount_avg = 0.0
            if hasattr(self, 'stat_labels') and 'mean_etch' in self.stat_labels:
                etch_text = self.stat_labels['mean_etch'].text()
                if etch_text and etch_text != "--":
                    etching_amount_avg = float(etch_text)
                    print(f"刻蚀量平均值: {etching_amount_avg}nm")

            # 根据刻蚀量平均值确定倍速规则（使用用户设定的阈值）
            threshold = self.speed_threshold
            if etching_amount_avg < threshold:
                # 小于阈值，不生成倍速Recipe
                print(f"刻蚀量平均值({etching_amount_avg}nm) < {threshold}nm，不生成倍速Recipe")
                return speed_recipes

            elif etching_amount_avg < 2 * threshold:
                # 阈值到2倍阈值，生成2倍速Recipe
                multiplier = 2
                scan_count = 2
                prefix = "2_scan_x2_speed_"
                description = "2倍速Recipe(扫描2次)"

            else:
                # 大于2倍阈值，生成3倍速Recipe
                multiplier = 3
                scan_count = 3
                prefix = "3_scan_x3_speed_"
                description = "3倍速Recipe(扫描3次)"

            # 生成倍速Recipe文件
            speed_filename = prefix + original_filename
            speed_recipe_path = os.path.join(self.output_dir, speed_filename)

            # 读取原始Recipe并生成倍速版本
            self._create_speed_recipe(original_recipe_path, speed_recipe_path, multiplier)

            speed_recipes.append({
                'multiplier': multiplier,
                'scan_count': scan_count,
                'filename': speed_filename,
                'path': speed_recipe_path,
                'description': description
            })

            print(f"已生成{description}: {speed_filename}")

        except Exception as e:
            print(f"生成倍速Recipe失败: {str(e)}")

        return speed_recipes

    def _create_speed_recipe(self, original_path, speed_path, multiplier):
        """
        创建倍速Recipe文件

        Args:
            original_path: 原始Recipe文件路径
            speed_path: 倍速Recipe输出路径
            multiplier: 速度倍数(2或3)
        """
        try:
            # 读取原始Recipe文件
            df = pd.read_csv(original_path)

            # 检查是否包含Y-Speed列
            if 'Y-Speed' not in df.columns:
                raise ValueError("Recipe文件中未找到'Y-Speed'列")

            # 对Y-Speed列应用倍数，但不超过500mm/s的上限
            df['Y-Speed'] = df['Y-Speed'].apply(
                lambda speed: min(speed * multiplier, 500.0) if speed > 0 else speed
            )

            # 保存倍速Recipe文件
            df.to_csv(speed_path, index=False)

            # 统计被速度限制的行数
            limited_count = sum(1 for _, row in df.iterrows()
                              if row['Y-Speed'] > 0 and row['Y-Speed'] == 500.0)

            if limited_count > 0:
                print(f"警告: {limited_count}行的Y-Speed达到500mm/s上限")

        except Exception as e:
            raise Exception(f"创建倍速Recipe失败: {str(e)}")

    def _generate_simulation_log(self):
        """
        生成模拟日志文件

        Returns:
            str: 生成的日志文件路径，如果失败返回None
        """
        try:
            # 准备模拟数据
            simulation_data = self._prepare_simulation_data()

            # 生成模拟日志（使用从UI读取的刻蚀时间）
            log_file_path = self.simulation_logger.generate_simulation_log(
                self.output_dir,
                simulation_data,
                simulation_data.get('etching_time_seconds')
            )

            return log_file_path

        except Exception as e:
            print(f"生成模拟日志失败: {str(e)}")
            return None

    def _prepare_simulation_data(self):
        """
        准备模拟数据字典 - 直接从UI的膜厚统计区域读取已计算好的数据

        Returns:
            Dict: 模拟数据字典
        """
        # 从配置管理器获取载台中心坐标
        config_manager = get_config_manager()

        # 准备基本模拟参数
        simulation_data = {
            'file_name': os.path.basename(self.etching_file) if self.etching_file else '',
            'grid_size': 240,  # 默认网格尺寸，可以根据需要调整
            'resolution': 1.0,  # 默认分辨率
            'wf_size': 150,  # 默认晶圆尺寸
            'target_thickness': self.target_thickness_input.value(),
            'stage_center_x': config_manager.get_stage_center_x(),
            'stage_center_y': config_manager.get_stage_center_y(),
            'y_step': int(self.y_step_combo.currentText()),
            'transition_width': self.transition_width,
            'recipe_range': self.recipe_range,
            'uniformity_threshold': self.uniformity_threshold,
            'speed_threshold': self.speed_threshold,  # 倍速多次扫描判定阈值
            'simulation_count': getattr(self, 'simulation_count', 1),
            'outlier_removal_count': getattr(self, 'outlier_removal_count', 0),
            'total_removed_points': getattr(self, 'total_removed_points', 0)
        }

        # 直接从UI的膜厚统计标签读取已计算好的统计数据
        try:
            # 读取初始膜厚统计（从UI标签）
            origin_stats = {}
            if hasattr(self, 'stat_labels') and 'max_initial' in self.stat_labels:
                origin_text = self.stat_labels['max_initial'].text()
                if origin_text != "--":
                    origin_stats['max'] = float(origin_text)

            if hasattr(self, 'stat_labels') and 'min_initial' in self.stat_labels:
                origin_text = self.stat_labels['min_initial'].text()
                if origin_text != "--":
                    origin_stats['min'] = float(origin_text)

            if hasattr(self, 'stat_labels') and 'mean_initial' in self.stat_labels:
                origin_text = self.stat_labels['mean_initial'].text()
                if origin_text != "--":
                    origin_stats['average'] = float(origin_text)

            if hasattr(self, 'stat_labels') and 'uniformity_initial' in self.stat_labels:
                origin_text = self.stat_labels['uniformity_initial'].text()
                if origin_text != "--":
                    origin_stats['uniformity'] = float(origin_text.replace('%', ''))

            # 计算Range（Max - Min）
            if 'max' in origin_stats and 'min' in origin_stats:
                origin_stats['range'] = origin_stats['max'] - origin_stats['min']

            simulation_data['origin_statistics'] = origin_stats
            print("从UI膜厚统计区域读取初始膜厚统计成功")

        except Exception as e:
            print(f"从UI读取初始膜厚统计失败: {str(e)}")
            simulation_data['origin_statistics'] = {
                'max': 0.0, 'min': 0.0, 'average': 0.0,
                'range': 0.0, 'uniformity': 0.0, 'count': 0
            }

        # 读取刻蚀后膜厚统计（从UI标签）
        try:
            simulated_stats = {}
            if hasattr(self, 'stat_labels') and 'max_result' in self.stat_labels:
                result_text = self.stat_labels['max_result'].text()
                if result_text != "--":
                    simulated_stats['max'] = float(result_text)

            if hasattr(self, 'stat_labels') and 'min_result' in self.stat_labels:
                result_text = self.stat_labels['min_result'].text()
                if result_text != "--":
                    simulated_stats['min'] = float(result_text)

            if hasattr(self, 'stat_labels') and 'mean_result' in self.stat_labels:
                result_text = self.stat_labels['mean_result'].text()
                if result_text != "--":
                    simulated_stats['average'] = float(result_text)

            if hasattr(self, 'stat_labels') and 'uniformity_result' in self.stat_labels:
                result_text = self.stat_labels['uniformity_result'].text()
                if result_text != "--":
                    simulated_stats['uniformity'] = float(result_text.replace('%', ''))

            # 计算Range（Max - Min）
            if 'max' in simulated_stats and 'min' in simulated_stats:
                simulated_stats['range'] = simulated_stats['max'] - simulated_stats['min']

            simulation_data['simulated_statistics'] = simulated_stats
            print("从UI膜厚统计区域读取刻蚀后膜厚统计成功")

        except Exception as e:
            print(f"从UI读取刻蚀后膜厚统计失败: {str(e)}")
            simulation_data['simulated_statistics'] = {
                'max': 0.0, 'min': 0.0, 'average': 0.0,
                'range': 0.0, 'uniformity': 0.0, 'count': 0
            }

        # 读取刻蚀量统计（从UI标签）
        try:
            etch_stats = {}
            if hasattr(self, 'stat_labels') and 'max_etch' in self.stat_labels:
                etch_text = self.stat_labels['max_etch'].text()
                if etch_text != "--":
                    etch_stats['max'] = float(etch_text)

            if hasattr(self, 'stat_labels') and 'min_etch' in self.stat_labels:
                etch_text = self.stat_labels['min_etch'].text()
                if etch_text != "--":
                    etch_stats['min'] = float(etch_text)

            if hasattr(self, 'stat_labels') and 'mean_etch' in self.stat_labels:
                etch_text = self.stat_labels['mean_etch'].text()
                if etch_text != "--":
                    etch_stats['average'] = float(etch_text)

            if hasattr(self, 'stat_labels') and 'uniformity_etch' in self.stat_labels:
                etch_text = self.stat_labels['uniformity_etch'].text()
                if etch_text != "--":
                    etch_stats['uniformity'] = float(etch_text.replace('%', ''))

            # 计算Range（Max - Min）
            if 'max' in etch_stats and 'min' in etch_stats:
                etch_stats['range'] = etch_stats['max'] - etch_stats['min']

            simulation_data['etching_statistics'] = etch_stats
            print("从UI膜厚统计区域读取刻蚀量统计成功")

        except Exception as e:
            print(f"从UI读取刻蚀量统计失败: {str(e)}")
            simulation_data['etching_statistics'] = {
                'max': 0.0, 'min': 0.0, 'average': 0.0,
                'range': 0.0, 'uniformity': 0.0, 'count': 0
            }

        # 读取刻蚀时间（从Recipe统计栏）
        try:
            etching_time_text = self.etch_time_value.text()
            if etching_time_text and etching_time_text != "--":
                # 解析时间格式（例如 "3分15秒"）
                time_parts = etching_time_text.replace('秒', '').replace('分', ':').split(':')
                if len(time_parts) == 2:
                    minutes = int(time_parts[0])
                    seconds = int(time_parts[1])
                    etching_time_seconds = minutes * 60 + seconds
                    simulation_data['etching_time_seconds'] = etching_time_seconds
                    print(f"从UI Recipe统计栏读取刻蚀时间: {etching_time_seconds}秒")
                else:
                    # 如果格式不同，尝试直接解析为秒数
                    simulation_data['etching_time_seconds'] = float(etching_time_text.replace('秒', ''))
            else:
                simulation_data['etching_time_seconds'] = None
        except Exception as e:
            print(f"读取刻蚀时间失败: {str(e)}")
            simulation_data['etching_time_seconds'] = None

        # 计算倍速多次扫描次数（根据刻蚀量平均值和阈值）
        try:
            etching_amount_avg = 0.0
            if hasattr(self, 'stat_labels') and 'mean_etch' in self.stat_labels:
                etch_text = self.stat_labels['mean_etch'].text()
                if etch_text and etch_text != "--":
                    etching_amount_avg = float(etch_text)

            threshold = self.speed_threshold
            if etching_amount_avg < threshold:
                plural_scan_time = 1  # 不生成倍速Recipe
            elif etching_amount_avg < 2 * threshold:
                plural_scan_time = 2  # 生成2倍速Recipe
            else:
                plural_scan_time = 3  # 生成3倍速Recipe

            simulation_data['plural_scan_time'] = plural_scan_time
            print(f"计算倍速多次扫描次数: {plural_scan_time}次 (刻蚀量={etching_amount_avg}nm, 阈值={threshold}nm)")

        except Exception as e:
            print(f"计算倍速多次扫描次数失败: {str(e)}")
            simulation_data['plural_scan_time'] = 1

        return simulation_data

    def start_batch_processing(self):
        """开始批量处理流程"""
        # 检查离子束文件是否已选择
        if not self.beam_file:
            QMessageBox.warning(self, "缺少文件", "请先选择离子束分布文件")
            return

        # 弹出多文件选择对话框
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("CSV文件 (*.csv);;所有文件 (*.*)")
        file_dialog.setWindowTitle("选择要批量处理的初始膜厚数据文件")

        if file_dialog.exec_() == QMessageBox.Accepted:
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.batch_file_list = selected_files
                self.current_batch_index = 0

                # 显示确认对话框
                file_names = [os.path.basename(f) for f in selected_files]
                file_list_str = ", ".join(file_names)

                reply = QMessageBox.question(
                    self,
                    "确认批量处理",
                    f"将以当前参数设置和离子束文件对以下文件进行批量处理：\n\n"
                    f"{file_list_str}\n\n"
                    f"是否继续？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )

                if reply == QMessageBox.Yes:
                    # 创建Lot_Recipe文件夹和记录开始时间
                    self.batch_start_time = time.time()
                    self.batch_time_str = time.strftime("%Y%m%d-%H%M%S")
                    self.lot_recipe_dir = self.create_lot_recipe_folder(selected_files[0])

                    # 修复：批量处理开始时，初始化etching_file为第一个文件的路径
                    if self.etching_file is None:
                        self.etching_file = selected_files[0]
                        print(f"[DEBUG] 批量处理开始，设置原始文件路径: {self.etching_file}")

                    self.is_batch_processing = True
                    self.batch_process_btn.setEnabled(False)
                    self.process_btn.setEnabled(False)
                    self.batch_process_btn.setText("批量处理中...")

                    # 开始处理第一个文件
                    self.process_next_batch_file()
            else:
                QMessageBox.information(self, "提示", "未选择任何文件")

    def create_lot_recipe_folder(self, first_file_path):
        """创建Lot_Recipe文件夹

        Args:
            first_file_path: 第一个文件的路径，用于确定文件夹位置

        Returns:
            str: Lot_Recipe文件夹路径
        """
        try:
            # 获取第一个文件所在目录
            file_dir = os.path.dirname(first_file_path)

            print(f"[DEBUG] 批量处理时间戳: {self.batch_time_str}")
            print(f"[DEBUG] 第一个文件路径: {first_file_path}")
            print(f"[DEBUG] 文件所在目录: {file_dir}")

            # 创建Lot_Recipe文件夹
            lot_recipe_dir = os.path.join(file_dir, f"{self.batch_time_str}_Lot_Recipe")
            print(f"[DEBUG] 准备创建Lot_Recipe文件夹: {lot_recipe_dir}")

            os.makedirs(lot_recipe_dir, exist_ok=True)

            # 验证文件夹是否成功创建
            if os.path.exists(lot_recipe_dir):
                print(f"[DEBUG] Lot_Recipe文件夹创建成功: {lot_recipe_dir}")
                print(f"[DEBUG] 文件夹权限: {oct(os.stat(lot_recipe_dir).st_mode)[-3:]}")
            else:
                print(f"[DEBUG] Lot_Recipe文件夹创建失败: {lot_recipe_dir}")
                return None

            return lot_recipe_dir

        except Exception as e:
            print(f"[DEBUG] 创建Lot_Recipe文件夹失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def backup_recipe_to_lot_folder(self, simulation_result_dir, file_name):
        """备份Recipe文件到Lot_Recipe文件夹
        优先备份倍速多次扫描Recipe，如果存在倍速Recipe则不备份原速度Recipe

        Args:
            simulation_result_dir: 模拟结果文件夹路径
            file_name: 原始文件名（不含扩展名）
        """
        try:
            print(f"[DEBUG] 开始备份Recipe: {file_name}")
            print(f"[DEBUG] Lot_Recipe文件夹路径: {self.lot_recipe_dir}")
            print(f"[DEBUG] 模拟结果文件夹路径: {simulation_result_dir}")

            if not self.lot_recipe_dir:
                print(f"[DEBUG] Lot_Recipe文件夹路径为空，跳过备份")
                return

            if not os.path.exists(self.lot_recipe_dir):
                print(f"[DEBUG] Lot_Recipe文件夹不存在，跳过备份: {self.lot_recipe_dir}")
                return

            if not os.path.exists(simulation_result_dir):
                print(f"[DEBUG] 模拟结果文件夹不存在，跳过备份: {simulation_result_dir}")
                return

            # 查找倍速Recipe文件（优先）
            base_name = file_name
            speed_recipes = []
            normal_recipes = []
            all_files = os.listdir(simulation_result_dir)

            print(f"[DEBUG] 在文件夹中查找Recipe文件: {simulation_result_dir}")
            print(f"[DEBUG] 所有文件: {[f for f in all_files if 'Recipe' in f]}")

            # 分类查找Recipe文件
            for filename in all_files:
                if "_Stage_Movement_Instruction_Recipe.csv" in filename:
                    if ("2_scan_" in filename or "3_scan_" in filename):
                        # 检查倍速Recipe是否包含base_name
                        if base_name in filename:
                            speed_recipes.append(filename)
                            print(f"[DEBUG] 找到倍速Recipe: {filename}")
                    elif filename.startswith(base_name) and not ("2_scan_" in filename or "3_scan_" in filename):
                        normal_recipes.append(filename)
                        print(f"[DEBUG] 找到普通Recipe: {filename}")

            print(f"[DEBUG] 倍速Recipe数量: {len(speed_recipes)}")
            print(f"[DEBUG] 普通Recipe数量: {len(normal_recipes)}")

            # 如果有倍速Recipe，只备份倍速Recipe，不备份原速度Recipe
            if speed_recipes:
                print(f"[DEBUG] 选择备份倍速Recipe: {speed_recipes}")
                for speed_recipe in speed_recipes:
                    src_path = os.path.join(simulation_result_dir, speed_recipe)
                    dst_path = os.path.join(self.lot_recipe_dir, speed_recipe)

                    if os.path.exists(src_path):
                        import shutil
                        shutil.copy2(src_path, dst_path)
                        print(f"[DEBUG] 成功备份倍速Recipe: {speed_recipe} -> {self.lot_recipe_dir}")
                    else:
                        print(f"[DEBUG] 倍速Recipe文件不存在: {src_path}")
                print(f"[DEBUG] {base_name} 存在倍速Recipe，已备份倍速Recipe，跳过原速度Recipe")
            elif normal_recipes:
                print(f"[DEBUG] 选择备份普通Recipe: {normal_recipes[0]}")
                filename = normal_recipes[0]
                src_path = os.path.join(simulation_result_dir, filename)
                dst_path = os.path.join(self.lot_recipe_dir, filename)

                if os.path.exists(src_path):
                    import shutil
                    shutil.copy2(src_path, dst_path)
                    print(f"[DEBUG] 成功备份普通Recipe: {filename} -> {self.lot_recipe_dir}")
                else:
                    print(f"[DEBUG] 普通Recipe文件不存在: {src_path}")
            else:
                print(f"[DEBUG] 未找到任何Recipe文件: {file_name}")

        except Exception as e:
            print(f"[DEBUG] 备份Recipe失败: {str(e)}")
            import traceback
            traceback.print_exc()

    def process_next_batch_file(self):
        """处理批量处理中的下一个文件"""
        if self.current_batch_index >= len(self.batch_file_list):
            # 所有文件处理完成
            self.finish_batch_processing()
            return

        current_file = self.batch_file_list[self.current_batch_index]
        file_name = os.path.basename(current_file)
        file_base_name = os.path.splitext(file_name)[0]
        file_dir = os.path.dirname(current_file)

        # 创建结果文件夹
        result_dir = os.path.join(file_dir, f"{file_base_name}_simulation_result")
        os.makedirs(result_dir, exist_ok=True)

        # 重置统计数据
        self.reset_process_statistics()
        self.clear_ui_statistics()

        # 设置当前处理的文件
        # 关键修复：保持原始文件路径不变，用于连续最小值删除
        if self.etching_file is None:
            self.etching_file = current_file  # 只在首次设置

        self.etching_label.setText(file_name)
        self.output_dir = result_dir
        self.output_label.setText(result_dir)

        # 显示处理进度
        progress_msg = f"批量处理进度：{self.current_batch_index + 1}/{len(self.batch_file_list)}\n正在处理：{file_name}"
        self.main_window.update_status_message(progress_msg)

        # 开始单片处理流程
        self.start_single_batch_processing(current_file, result_dir)

    def start_single_batch_processing(self, etching_file, output_dir):
        """开始单片批量处理"""
        try:
            # 初始化处理器
            grid_size = float(self.grid_size_combo.currentText())
            resolution = float(self.resolution_combo.currentText())
            wafer_diameter = float(self.wafer_diameter_combo.currentText())
            target_thickness = self.target_thickness_input.value()

            self.processor = IonBeamProcessor(
                grid_size=grid_size,
                resolution=resolution,
                wafer_diameter=wafer_diameter,
                transition_width=self.transition_width
            )

            # 设置目标膜厚
            self.processor.set_target_thickness(target_thickness)

            # 关键修复：不要更新self.etching_file，让它始终指向批量处理的原始文件
            # 这样在连续最小值删除时，始终能获取到原始1903.csv路径
            print(f"[DEBUG] start_single_batch_processing: etching_file={etching_file}, self.etching_file={self.etching_file}")

            # 运行模拟
            self.simulation_thread = SimulationThread(
                self.processor,
                etching_file,
                self.beam_file,
                output_dir
            )
            self.simulation_thread.results_ready.connect(self.on_batch_simulation_complete)
            self.simulation_thread.error_occurred.connect(self.on_batch_simulation_error)
            self.simulation_thread.start()

        except Exception as e:
            self.on_batch_simulation_error(str(e))

    def on_batch_simulation_complete(self, results):
        """批量单片模拟完成处理"""
        try:
            print(f"[DEBUG] on_batch_simulation_complete 开始执行")
            if results:
                print(f"[DEBUG] 准备更新图表面板（批量处理模式）")
                # 在批量处理模式中，暂时跳过图表更新以避免matplotlib问题
                # self.update_plots()
                print(f"[DEBUG] 跳过图表更新，直接更新统计信息")

                # 更新统计信息
                initial_stats = results.get('initial_thickness_stats', {})
                target_thickness = results.get('target_thickness', 0)
                validated_stats = results.get('validated_thickness_stats', {})
                etch_stats = self.processor.calculate_etch_amount_stats()

                print(f"[DEBUG] 开始更新统计标签")
                self.update_stat_labels(initial_stats, target_thickness, validated_stats, etch_stats)
                print(f"[DEBUG] 统计标签更新完成")

                # 检查均一性是否达标
                unity_msg = ""
                if 'uniformity' in validated_stats:
                    unity = validated_stats['uniformity']
                    icon = "✅" if unity <= self.uniformity_threshold else "❌"
                    unity_msg = f"\n\n验算均一性: {unity:.2f}% {icon} (阈值: {self.uniformity_threshold:.2f}%)"

                print(f"[DEBUG] 均一性检查完成: unity={unity if 'uniformity' in validated_stats else 'N/A'}, threshold={self.uniformity_threshold}")

                # 更新异常值处理器的阈值
                print(f"[DEBUG] 开始设置异常值处理器")
                self.outlier_processor.uniformity_threshold = self.uniformity_threshold

                # 设置批量处理模式的回调
                self.outlier_processor.set_simulation_callback(self.restart_batch_simulation_with_optimized_data)

                # 设置批量处理的特殊处理
                if hasattr(self.outlier_processor, 'set_batch_mode'):
                    self.outlier_processor.set_batch_mode(True)

                # 关键修复：确保在调用异常值处理器之前，原始文件路径是正确的
                # 这样即使在handle_simulation_completed中的多次调用，也能正确传递给异常值处理器
                print(f"[DEBUG] 在调用异常值处理器前设置原始文件路径")
                print(f"[DEBUG] self.etching_file: {self.etching_file}")
                self.outlier_processor.original_file = self.etching_file  # 设置原始文件路径
                results['original_etching_file'] = self.etching_file
                print(f"[DEBUG] results中的original_etching_file: {results.get('original_etching_file', 'None')}")
                print(f"[DEBUG] 异常值处理器设置完成")

                # 处理模拟完成，可能启动异常值优化
                print(f"[DEBUG] 开始调用异常值处理器.handle_simulation_completed (批量模式，但使用单片交互流程)")
                self.outlier_processor.handle_simulation_completed(results, unity_msg, validated_stats, auto_optimize=False)
                print(f"[DEBUG] 异常值处理器.handle_simulation_completed 调用完成")
            else:
                QMessageBox.critical(self, "错误", "批量模拟过程中发生错误")
                self.next_batch_file_or_finish()

        except Exception as e:
            self.on_batch_simulation_error(str(e))

    def on_batch_simulation_error(self, error_message):
        """批量模拟错误处理"""
        current_file_name = os.path.basename(self.batch_file_list[self.current_batch_index])

        reply = QMessageBox.question(
            self,
            "模拟错误",
            f"文件 {current_file_name} 模拟过程中发生错误:\n{error_message}\n\n"
            f"是否跳过此文件继续处理下一个？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            self.next_batch_file_or_finish()
        else:
            self.finish_batch_processing()

    def restart_batch_simulation_with_optimized_data(self, new_file_path, new_data):
        """使用优化后的数据重新启动批量模拟"""
        try:
            self.main_window.update_status_message(f"使用优化数据 {os.path.basename(new_file_path)} 开始重新模拟...")
            self.increment_simulation_count()

            # 关键修复：不要更新self.etching_file，让它始终指向批量处理的原始文件
            # 这样在连续最小值删除时，始终能获取到原始1903.csv路径
            print(f"[DEBUG] restart_batch_simulation_with_optimized_data: new_file_path={new_file_path}, self.etching_file={self.etching_file}")

            # 关键修复：创建自定义SimulationThread，确保original_etching_file始终传递
            simulation_thread = CustomSimulationThread(
                self.processor,
                new_file_path,
                self.beam_file,
                self.output_dir,
                self.etching_file  # 始终传递原始的batch文件路径
            )

            simulation_thread.results_ready.connect(self.on_batch_simulation_complete)
            simulation_thread.error_occurred.connect(self.on_batch_simulation_error)
            simulation_thread.start()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"重新启动批量模拟失败: {str(e)}")
            self.next_batch_file_or_finish()

    def on_optimized_batch_simulation_completed(self, results):
        """优化数据批量模拟完成处理"""
        try:
            print(f"[DEBUG] on_optimized_batch_simulation_completed 开始执行")
            # 在批量处理模式中，暂时跳过图表更新以避免matplotlib问题
            # self.update_plots()
            print(f"[DEBUG] 跳过图表更新")

            # 更新统计信息
            initial_stats = results.get('initial_thickness_stats', {})
            target_thickness = results.get('target_thickness', 0)
            validated_stats = results.get('validated_thickness_stats', {})
            etch_stats = self.processor.calculate_etch_amount_stats()

            print(f"[DEBUG] 开始更新统计信息")
            self.update_stat_labels(initial_stats, target_thickness, validated_stats, etch_stats)
            print(f"[DEBUG] 统计信息更新完成")

            # 检查均一性是否达标
            unity_msg = ""
            if 'uniformity' in validated_stats:
                unity = validated_stats['uniformity']
                icon = "✅" if unity <= self.uniformity_threshold else "❌"
                unity_msg = f"\n\n验算均一性: {unity:.2f}% {icon} (阈值: {self.uniformity_threshold:.2f}%)"

                # 如果仍不达标，继续处理
                if unity > self.uniformity_threshold:
                    self.outlier_processor.handle_simulation_completed(results, unity_msg, validated_stats)
                    return

            # 均一性达标，单片模拟完成
            self.complete_single_batch_simulation()

        except Exception as e:
            self.on_batch_simulation_error(str(e))

    def complete_single_batch_simulation(self):
        """完成单片批量处理"""
        current_file_name = os.path.basename(self.batch_file_list[self.current_batch_index])
        print(f"[DEBUG] 开始完成单片批量处理: {current_file_name}")

        # 生成统计报告对话框
        stats_msg = self.generate_statistics_report()

        print(f"[DEBUG] 准备显示单片模拟完成对话框: {current_file_name}")
        reply = QMessageBox.question(
            self,
            "单片模拟完成",
            f"文件 {current_file_name} 模拟已完成！\n\n{stats_msg}\n\n"
            f"是否要生成载台运动速度Recipe？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        print(f"[DEBUG] 用户选择 (Yes=16384): {reply} for {current_file_name}")

        if reply == QMessageBox.Yes:
            try:
                print(f"[DEBUG] 开始生成Recipe: {current_file_name}")
                # 生成载台运动速度Recipe
                self.generate_stage_speed_map()
                print(f"[DEBUG] Recipe生成完成: {current_file_name}")

                # 显示Recipe统计信息
                recipe_info = f"Recipe已生成！\n"
                recipe_info += f"行数: {self.recipe_rows_value.text()}\n"
                recipe_info += f"刻蚀时间: {self.etch_time_value.text()}"

                print(f"[DEBUG] 准备显示Recipe生成完成对话框: {current_file_name}")
                QMessageBox.information(self, "Recipe生成完成", recipe_info)
                print(f"[DEBUG] Recipe生成完成对话框已显示: {current_file_name}")

                # 生成模拟日志
                try:
                    print(f"[DEBUG] 开始生成模拟日志: {current_file_name}")
                    simulation_log_path = self._generate_simulation_log()
                    if simulation_log_path:
                        log_filename = os.path.basename(simulation_log_path)
                        self.main_window.update_status_message(f"模拟日志已生成: {log_filename}")
                        print(f"[DEBUG] 模拟日志生成完成: {log_filename}")
                except Exception as log_e:
                    print(f"[DEBUG] 生成模拟日志失败: {str(log_e)}")
                    self.main_window.update_status_message(f"生成模拟日志失败: {str(log_e)}")

            except Exception as e:
                print(f"[DEBUG] Recipe生成异常: {str(e)} for {current_file_name}")
                QMessageBox.critical(self, "错误", f"生成Recipe失败: {str(e)}")

        print(f"[DEBUG] 准备处理下一个文件: {current_file_name}")

        # 备份Recipe到Lot_Recipe文件夹
        try:
            base_name = os.path.splitext(current_file_name)[0]
            self.backup_recipe_to_lot_folder(self.output_dir, base_name)
            print(f"[DEBUG] Recipe备份完成: {current_file_name}")
        except Exception as e:
            print(f"[DEBUG] Recipe备份失败: {str(e)}")

        # 继续处理下一个文件
        self.next_batch_file_or_finish()
        print(f"[DEBUG] next_batch_file_or_finish 调用完成: {current_file_name}")

    def next_batch_file_or_finish(self):
        """继续处理下一个文件或完成批量处理"""
        self.current_batch_index += 1

        if self.current_batch_index < len(self.batch_file_list):
            current_file_name = os.path.basename(self.batch_file_list[self.current_batch_index])

            reply = QMessageBox.question(
                self,
                "继续批量处理",
                f"{os.path.basename(self.batch_file_list[self.current_batch_index - 1])} 的处理已完成。\n\n"
                f"是否继续处理下一个文件 {current_file_name}？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self.process_next_batch_file()
            else:
                self.finish_batch_processing()
        else:
            self.finish_batch_processing()

    def finish_batch_processing(self):
        """完成批量处理"""
        try:
            # 汇总所有Log文件
            self.generate_batch_simulation_log()

            self.is_batch_processing = False
            self.batch_process_btn.setEnabled(True)
            self.process_btn.setEnabled(True)
            self.batch_process_btn.setText("以当前设置参数及Beam强度进行批量处理")

            QMessageBox.information(self, "批量处理完成", "所有文件的处理已完成！Log汇总文件已生成。")
            self.main_window.update_status_message("批量处理完成")

        except Exception as e:
            print(f"[DEBUG] 生成Log汇总文件失败: {str(e)}")
            self.is_batch_processing = False
            self.batch_process_btn.setEnabled(True)
            self.process_btn.setEnabled(True)
            self.batch_process_btn.setText("以当前设置参数及Beam强度进行批量处理")
            QMessageBox.information(self, "批量处理完成", "所有文件的处理已完成！但Log汇总生成失败。")

    def generate_statistics_report(self):
        """生成统计报告"""
        try:
            report = "=== 膜厚统计 ===\n"

            # 初始膜厚统计
            if hasattr(self, 'stat_labels'):
                initial_min = self.stat_labels['min_initial'].text()
                initial_max = self.stat_labels['max_initial'].text()
                initial_mean = self.stat_labels['mean_initial'].text()
                initial_uniformity = self.stat_labels['uniformity_initial'].text()

                report += f"初始膜厚: 最小值={initial_min}nm, 最大值={initial_max}nm, "
                report += f"平均值={initial_mean}nm, 均一性={initial_uniformity}\n"

                # 刻蚀后膜厚统计
                result_min = self.stat_labels['min_result'].text()
                result_max = self.stat_labels['max_result'].text()
                result_mean = self.stat_labels['mean_result'].text()
                result_uniformity = self.stat_labels['uniformity_result'].text()

                report += f"刻蚀后膜厚: 最小值={result_min}nm, 最大值={result_max}nm, "
                report += f"平均值={result_mean}nm, 均一性={result_uniformity}\n"

                # 刻蚀量统计
                etch_min = self.stat_labels['min_etch'].text()
                etch_max = self.stat_labels['max_etch'].text()
                etch_mean = self.stat_labels['mean_etch'].text()
                etch_uniformity = self.stat_labels['uniformity_etch'].text()

                report += f"刻蚀量: 最小值={etch_min}nm, 最大值={etch_max}nm, "
                report += f"平均值={etch_mean}nm, 均一性={etch_uniformity}\n"

            report += "\n=== 模拟过程统计 ===\n"

            # 模拟过程统计
            if hasattr(self, 'process_stat_labels'):
                sim_count = self.process_stat_labels['simulation_count'].text()
                outlier_count = self.process_stat_labels['outlier_removal_count'].text()
                removed_points = self.process_stat_labels['total_removed_points'].text()

                report += f"模拟次数: {sim_count}\n"
                report += f"异常值剔除次数: {outlier_count}\n"
                report += f"已剔除异常点个数: {removed_points}"

            return report

        except Exception as e:
            return f"生成统计报告失败: {str(e)}"

    def generate_batch_simulation_log(self):
        """生成批量处理汇总Log文件"""
        try:
            print(f"[DEBUG] 开始生成批量处理汇总Log文件")

            # 构建汇总Log文件路径
            if not self.batch_file_list:
                print(f"[DEBUG] 批量文件列表为空，跳过Log汇总")
                return

            batch_time_str = self.batch_time_str
            base_dir = os.path.dirname(self.batch_file_list[0])
            log_file_path = os.path.join(base_dir, f"{batch_time_str}_Batch_Simulation_Log.csv")

            # 收集所有模拟结果文件夹
            result_dirs = []
            for file_path in self.batch_file_list:
                file_name = os.path.basename(file_path)
                base_name = os.path.splitext(file_name)[0]
                result_dir = os.path.join(os.path.dirname(file_path), f"{base_name}_simulation_result")
                result_dirs.append((result_dir, base_name))

            # 收集所有Log文件数据
            log_data = []
            for result_dir, base_name in result_dirs:
                log_file = os.path.join(result_dir, f"{base_name}_simulation_log.csv")
                if os.path.exists(log_file):
                    try:
                        log_content = self.read_simulation_log(log_file)
                        log_data.append((base_name, log_content))
                        print(f"[DEBUG] 读取Log文件: {base_name}_simulation_log.csv")
                    except Exception as e:
                        print(f"[DEBUG] 读取Log文件失败 {base_name}: {str(e)}")
                        log_data.append((base_name, {}))
                else:
                    print(f"[DEBUG] Log文件不存在: {base_name}_simulation_log.csv")
                    log_data.append((base_name, {}))

            # 创建汇总Log文件
            self.write_batch_simulation_log(log_file_path, log_data)

            print(f"[DEBUG] 批量处理Log汇总完成: {os.path.basename(log_file_path)}")

        except Exception as e:
            print(f"[DEBUG] 生成批量处理Log汇总失败: {str(e)}")
            raise e

    def read_simulation_log(self, log_file_path):
        """读取单个模拟Log文件

        Args:
            log_file_path: Log文件路径

        Returns:
            dict: Log文件内容解析为字典
        """
        log_data = {}
        try:
            with open(log_file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                lines = content.split('\n')

                # 读取参数设置部分（第3-13行）
                if len(lines) > 2:
                    log_data['parameters'] = {}
                    for i in range(2, min(13, len(lines))):
                        if ':' in lines[i]:
                            key, value = lines[i].split(':', 1)
                            log_data['parameters'][key.strip()] = value.strip()

                # 读取文件信息部分（第14行开始）
                if len(lines) > 13:
                    log_data['file_info'] = {}
                    # 文件信息字段（根据实际Log格式调整）
                    fields = [
                        '文件名', '初始膜厚统计', '目标膜厚', '刻蚀深度统计',
                        '刻蚀后膜厚统计', '刻蚀量统计', '停留时间统计',
                        '载台运动Recipe统计', '模拟过程统计'
                    ]

                    # 这里需要根据实际的Log格式来解析
                    # 由于不知道具体的Log格式，我们保留原始行数据
                    log_data['file_info']['raw_lines'] = lines[13:] if len(lines) > 13 else []

        except Exception as e:
            print(f"[DEBUG] 读取Log文件内容失败: {str(e)}")

        return log_data

    def write_batch_simulation_log(self, log_file_path, log_data):
        """写入批量处理汇总Log文件
        严格按照参考文件的CSV格式生成

        Args:
            log_file_path: 汇总Log文件路径
            log_data: 所有文件的数据列表 [(base_name, log_content), ...]
        """
        try:
            with open(log_file_path, 'w', encoding='utf-8-sig') as f:
                # 第一行：日期 - CSV格式
                current_date = time.strftime("%Y%m%d")
                f.write(f"Date,{current_date}\n")

                # 第二行：时间 - CSV格式
                start_time_str = time.strftime("%H:%M:%S", time.localtime(self.batch_start_time))
                f.write(f"Time,{start_time_str}\n")

                # 获取参数设置并写入第3-13行
                parameters = self.get_current_parameters_for_log()

                # 第3-13行：参数设置 - 严格按照参考格式
                param_lines = [
                    f"Grid_size(mm),{parameters.get('grid_size', 'N/A')}",
                    f"Resolution(mm/pixel),{parameters.get('resolution', 'N/A')}",
                    f"WF_size(mm),{parameters.get('wf_size', 'N/A')}",
                    f"Target(nm),{parameters.get('target', 'N/A')}",
                    f"Stage_center_X,{parameters.get('stage_center_x', 'N/A')}",
                    f"Stage_center_Y,{parameters.get('stage_center_y', 'N/A')}",
                    f"y-step,{parameters.get('y_step', 'N/A')}",
                    f"Transition_area_Width(mm),{parameters.get('transition_width', 'N/A')}",
                    f"Recipe_Length(nm),{parameters.get('recipe_length', 'N/A')}",
                    f"Result_Judge_Criteria(%),{parameters.get('uniformity_threshold', 'N/A')}",
                    f"Plural_Scan_Judge_Criteria(nm),{parameters.get('plural_scan_threshold', 'N/A')}"
                ]

                for line in param_lines:
                    f.write(line + "\n")

                # 第14行：文件编号
                file_names = [item[0] for item in log_data]
                wf_no_line = "WF_No.," + ",".join(file_names)
                f.write(wf_no_line + "\n")

                # 第15-30行：模拟数据
                # 从各个文件中提取数据并按行写入
                simulation_data = self.extract_simulation_data(log_data)

                data_lines = [
                    f"simulation_time,{simulation_data.get('simulation_time', [])}",
                    f"error_deleted_time,{simulation_data.get('error_deleted_time', [])}",
                    f"Deleted_points,{simulation_data.get('deleted_points', [])}",
                    f"Origin_Max(nm),{simulation_data.get('origin_max', [])}",
                    f"Origin_Min(nm),{simulation_data.get('origin_min', [])}",
                    f"Origin_Average(nm),{simulation_data.get('origin_average', [])}",
                    f"Origin_Range(nm),{simulation_data.get('origin_range', [])}",
                    f"Origin_Uniformity(%),{simulation_data.get('origin_uniformity', [])}",
                    f"Simulated_Max(nm),{simulation_data.get('simulated_max', [])}",
                    f"Simulated_Min(nm),{simulation_data.get('simulated_min', [])}",
                    f"Simulated_Average(nm),{simulation_data.get('simulated_average', [])}",
                    f"Simulated_Range(nm),{simulation_data.get('simulated_range', [])}",
                    f"Simulated_Uniformity(%),{simulation_data.get('simulated_uniformity', [])}",
                    f"Ave_Etching_amount(nm),{simulation_data.get('ave_etching_amount', [])}",
                    f"Plural_Scan_Time,{simulation_data.get('plural_scan_time', [])}",
                    f"Etching_time(s),{simulation_data.get('etching_time', [])}"
                ]

                for line in data_lines:
                    f.write(line + "\n")

            print(f"[DEBUG] 批量处理Log文件写入成功: {log_file_path}")

        except Exception as e:
            print(f"[DEBUG] 写入批量处理Log文件失败: {str(e)}")
            raise e

    def get_current_parameters_for_log(self):
        """获取当前参数设置（用于Log文件，按照参考格式）"""
        parameters = {}
        try:
            # 基本参数 - 按照参考文件的格式
            parameters['grid_size'] = self.grid_size_combo.currentText()
            parameters['resolution'] = self.resolution_combo.currentText()
            parameters['wf_size'] = self.wafer_diameter_combo.currentText()
            parameters['target'] = f"{self.target_thickness_input.value()}"
            parameters['stage_center_x'] = f"{self.stage_center_x.value()}"
            parameters['stage_center_y'] = f"{self.stage_center_y.value()}"
            parameters['y_step'] = self.y_step_combo.currentText()

            # 高级参数 - 按照参考文件的格式
            if hasattr(self, 'transition_width'):
                parameters['transition_width'] = f"{self.transition_width}"
            if hasattr(self, 'uniformity_threshold'):
                parameters['uniformity_threshold'] = f"{self.uniformity_threshold:.1f}"
            if hasattr(self, 'speed_threshold'):
                parameters['recipe_length'] = f"{self.speed_threshold}"
            else:
                parameters['recipe_length'] = "160"  # 默认值
            if hasattr(self, 'plural_scan_threshold'):
                parameters['plural_scan_threshold'] = f"{self.plural_scan_threshold}"
            else:
                parameters['plural_scan_threshold'] = "140"  # 默认值

        except Exception as e:
            print(f"[DEBUG] 获取参数设置失败: {str(e)}")

        return parameters

    def get_current_parameters(self):
        """获取当前参数设置"""
        parameters = {}
        try:
            # 基本参数
            parameters['网格尺寸'] = self.grid_size_combo.currentText()
            parameters['分辨率'] = self.resolution_combo.currentText()
            parameters['晶圆直径'] = self.wafer_diameter_combo.currentText()
            parameters['目标膜厚'] = f"{self.target_thickness_input.value()} nm"

            # 载台参数
            parameters['载台中心X'] = f"{self.stage_center_x.value()} mm"
            parameters['载台中心Y'] = f"{self.stage_center_y.value()} mm"
            parameters['Y-Step步长'] = f"{self.y_step_combo.currentText()}"

            # 高级参数
            if hasattr(self, 'transition_width'):
                parameters['过渡区宽度'] = f"{self.transition_width} mm"
            if hasattr(self, 'uniformity_threshold'):
                parameters['均一性阈值'] = f"{self.uniformity_threshold:.2f}%"
            if hasattr(self, 'speed_threshold'):
                parameters['刻蚀量阈值'] = f"{self.speed_threshold} nm"
            if hasattr(self, 'recipe_range'):
                parameters['Recipe截取范围'] = f"{self.recipe_range} mm"

        except Exception as e:
            print(f"[DEBUG] 获取参数设置失败: {str(e)}")

        return parameters

    def extract_simulation_data(self, log_data):
        """从各文件的Log数据中提取模拟数据

        Args:
            log_data: 所有文件的数据列表 [(base_name, log_content), ...]

        Returns:
            dict: 按照参考格式组织的模拟数据
        """
        simulation_data = {
            'simulation_time': [],
            'error_deleted_time': [],
            'deleted_points': [],
            'origin_max': [],
            'origin_min': [],
            'origin_average': [],
            'origin_range': [],
            'origin_uniformity': [],
            'simulated_max': [],
            'simulated_min': [],
            'simulated_average': [],
            'simulated_range': [],
            'simulated_uniformity': [],
            'ave_etching_amount': [],
            'plural_scan_time': [],
            'etching_time': []
        }

        try:
            for base_name, log_content in log_data:
                # 尝试从模拟结果文件夹读取单个Log文件
                result_dir = os.path.join(os.path.dirname(self.batch_file_list[0]), f"{base_name}_simulation_result")
                log_file = os.path.join(result_dir, f"{base_name}_simulation_log.csv")

                if os.path.exists(log_file):
                    file_data = self.parse_single_simulation_log(log_file)
                    for key in simulation_data:
                        simulation_data[key].append(file_data.get(key, 'N/A'))
                else:
                    # 如果Log文件不存在，填充默认值
                    for key in simulation_data:
                        simulation_data[key].append('N/A')

            # 转换为逗号分隔的字符串
            for key in simulation_data:
                if all(isinstance(x, (int, float)) for x in simulation_data[key] if x != 'N/A'):
                    # 如果是数值列表，格式化为带一位小数的字符串
                    simulation_data[key] = ",".join([f"{float(x):.1f}" if x != 'N/A' else 'N/A' for x in simulation_data[key]])
                else:
                    simulation_data[key] = ",".join([str(x) for x in simulation_data[key]])

        except Exception as e:
            print(f"[DEBUG] 提取模拟数据失败: {str(e)}")
            # 填充默认值
            for key in simulation_data:
                simulation_data[key] = ",".join(['N/A'] * len(log_data))

        return simulation_data

    def parse_single_simulation_log(self, log_file_path):
        """解析单个模拟Log文件，提取具体数值

        Args:
            log_file_path: 单个Log文件路径

        Returns:
            dict: 解析出的数据字典
        """
        data = {}
        try:
            with open(log_file_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()

            # 解析每一行，提取数值
            for line in lines:
                line = line.strip()
                if ',' in line:
                    key, value = line.split(',', 1)
                    key = key.strip()
                    value = value.strip()

                    # 映射参考文件中的字段名
                    if 'simulation_time' in key:
                        data['simulation_time'] = value
                    elif 'error_deleted_time' in key:
                        data['error_deleted_time'] = value
                    elif 'Deleted_points' in key:
                        data['deleted_points'] = value
                    elif 'Origin_Max' in key:
                        data['origin_max'] = value
                    elif 'Origin_Min' in key:
                        data['origin_min'] = value
                    elif 'Origin_Average' in key:
                        data['origin_average'] = value
                    elif 'Origin_Range' in key:
                        data['origin_range'] = value
                    elif 'Origin_Uniformity' in key:
                        data['origin_uniformity'] = value
                    elif 'Simulated_Max' in key:
                        data['simulated_max'] = value
                    elif 'Simulated_Min' in key:
                        data['simulated_min'] = value
                    elif 'Simulated_Average' in key:
                        data['simulated_average'] = value
                    elif 'Simulated_Range' in key:
                        data['simulated_range'] = value
                    elif 'Simulated_Uniformity' in key:
                        data['simulated_uniformity'] = value
                    elif 'Ave_Etching_amount' in key:
                        data['ave_etching_amount'] = value
                    elif 'Plural_Scan_Time' in key:
                        data['plural_scan_time'] = value
                    elif 'Etching_time' in key:
                        data['etching_time'] = value

        except Exception as e:
            print(f"[DEBUG] 解析单个Log文件失败 {log_file_path}: {str(e)}")

        return data

    def check_recipe_generated(self, base_name):
        """检查指定文件是否生成了Recipe

        Args:
            base_name: 文件基础名

        Returns:
            bool: 是否生成了Recipe
        """
        try:
            if not self.batch_file_list:
                return False

            # 查找对应的模拟结果文件夹
            for file_path in self.batch_file_list:
                if base_name in file_path:
                    result_dir = os.path.join(os.path.dirname(file_path), f"{base_name}_simulation_result")
                    if os.path.exists(result_dir):
                        # 检查是否有倍速Recipe
                        for filename in os.listdir(result_dir):
                            if (filename.startswith(base_name) and
                                ("2_scan_" in filename or "3_scan_" in filename) and
                                filename.endswith("_Stage_Movement_Instruction_Recipe.csv")):
                                return True
                        # 检查是否有普通Recipe
                        smi_file = os.path.join(result_dir, f"{base_name}_Stage_Movement_Instruction_Recipe.csv")
                        if os.path.exists(smi_file):
                            return True
                    break
        except Exception as e:
            print(f"[DEBUG] 检查Recipe生成状态失败: {str(e)}")

        return False

    def clear_ui_statistics(self):
        """清除UI统计显示"""
        try:
            # 清除膜厚统计
            for key in self.stat_labels:
                self.stat_labels[key].setText("--")
                self.stat_labels[key].setStyleSheet("")

            # 清除模拟过程统计
            self.process_stat_labels['simulation_count'].setText("0")
            self.process_stat_labels['outlier_removal_count'].setText("0")
            self.process_stat_labels['total_removed_points'].setText("0")

            # 清除Recipe统计
            self.recipe_rows_value.setText("--")
            self.etch_time_value.setText("--")

            # 清除图表
            self.init_plots()

        except Exception as e:
            print(f"清除UI统计失败: {str(e)}")

class SimulationThread(QThread):
    """在后台运行刻蚀模拟的线程"""
    results_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, processor, etching_file, beam_file, output_dir):
        super().__init__()
        self.processor = processor
        self.etching_file = etching_file
        self.beam_file = beam_file
        self.output_dir = output_dir

    def run(self):
        try:
            print(f"[DEBUG] SimulationThread开始运行")
            print(f"[DEBUG] etching_file: {self.etching_file}")
            results = self.processor.process_etching_simulation(
                self.etching_file,
                self.beam_file,
                self.output_dir
            )
            print(f"[DEBUG] SimulationThread即将返回results")
            self.results_ready.emit(results)
        except Exception as e:
            print(f"[DEBUG] SimulationThread异常: {str(e)}")
            self.error_occurred.emit(str(e))

class CustomSimulationThread(QThread):
    """自定义模拟线程，确保original_etching_file始终传递"""
    results_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, processor, etching_file, beam_file, output_dir, original_etching_file):
        super().__init__()
        self.processor = processor
        self.etching_file = etching_file
        self.beam_file = beam_file
        self.output_dir = output_dir
        self.original_etching_file = original_etching_file  # 原始batch文件路径

    def run(self):
        try:
            print(f"[DEBUG] CustomSimulationThread开始运行")
            print(f"[DEBUG] etching_file: {self.etching_file}")
            print(f"[DEBUG] original_etching_file: {self.original_etching_file}")

            results = self.processor.process_etching_simulation(
                self.etching_file,
                self.beam_file,
                self.output_dir
            )

            # 关键修复：确保original_etching_file始终包含在results中
            if 'original_etching_file' not in results:
                print(f"[DEBUG] 在results中添加original_etching_file: {self.original_etching_file}")
                results['original_etching_file'] = self.original_etching_file
            else:
                print(f"[DEBUG] results中已有original_etching_file: {results['original_etching_file']}")

            self.results_ready.emit(results)

        except Exception as e:
            print(f"[DEBUG] CustomSimulationThread异常: {str(e)}")
            self.error_occurred.emit(str(e))

# 测试CustomSimulationThread是否正确定义
print(f"[DEBUG] CustomSimulationThread类已加载")

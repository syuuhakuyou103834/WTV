import os
import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QMessageBox,
    QSizePolicy, QLineEdit
)
from PyQt5.QtGui import QDoubleValidator  
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

class BatchStatisticsDialog(QDialog):
    def __init__(self, wafer_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量晶圆膜厚统计")
        self.setGeometry(100, 100, 1200, 850)  # 增加窗口高度以容纳新组件
        
        # 存储格式 (filename, data)
        self.wafer_data = wafer_data
        self.current_page = 0
        self.per_page = 25  # 每页最多25个晶圆
        
        # 目标值默认为None（不显示）
        self.target_value = None
        
        # 计算数据页数
        self.total_pages = max(1, (len(wafer_data) - 1) // self.per_page + 1)
        
        # 初始化UI
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # ==== 新增：目标值控制行 ====
        target_layout = QHBoxLayout()
        
        # 目标值标签
        target_label = QLabel("目标值 (nm):")
        target_layout.addWidget(target_label)
        
        # 目标值输入框
        self.target_edit = QLineEdit()
        self.target_edit.setFixedWidth(150)
        self.target_edit.setValidator(QDoubleValidator())  # 只允许输入数字
        self.target_edit.setPlaceholderText("输入目标厚度值")
        target_layout.addWidget(self.target_edit)
        
        # 目标值应用按钮
        apply_target_btn = QPushButton("应用目标线")
        apply_target_btn.setFixedWidth(130)
        apply_target_btn.clicked.connect(self.apply_target_value)
        target_layout.addWidget(apply_target_btn)
        
        # 目标值清除按钮
        clear_target_btn = QPushButton("清除目标线")
        clear_target_btn.setFixedWidth(130)
        clear_target_btn.clicked.connect(self.clear_target_value)
        target_layout.addWidget(clear_target_btn)
        
        # 添加弹性空间
        target_layout.addStretch(1)
        
        main_layout.addLayout(target_layout)
        
        # ==== 导航栏 ====
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("上一页")
        self.prev_btn.setFixedWidth(100)
        self.prev_btn.clicked.connect(self.prev_page)
        nav_layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel(f"页面: {self.current_page+1}/{self.total_pages}")
        nav_layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("下一页")
        self.next_btn.setFixedWidth(100)
        self.next_btn.clicked.connect(self.next_page)
        nav_layout.addWidget(self.next_btn)
        
        main_layout.addLayout(nav_layout)
        
        # ==== 创建绘图区域 ====
        self.figure = Figure(figsize=(12, 8))
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas)
        
        # 初始绘图
        self.draw_boxplots()
        
        # 设置窗口大小策略
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
    def apply_target_value(self):
        """应用目标值并重新绘制图表"""
        try:
            # 从输入框获取值
            target_text = self.target_edit.text().strip()
            
            if target_text:  # 如果输入非空
                self.target_value = float(target_text)
                self.draw_boxplots()  # 重新绘制带目标线的图表
            else:
                QMessageBox.information(self, "提示", "请输入目标值")
                
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数值")
    
    def clear_target_value(self):
        """清除目标线并重新绘制图表"""
        self.target_value = None
        self.draw_boxplots()
    
    def draw_boxplots(self):
        """绘制当前页的箱型图"""
        self.figure.clear()
        
        if not self.wafer_data:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, '没有可用于统计的数据', 
                    ha='center', va='center', fontsize=12)
            ax.axis('off')
            self.canvas.draw()
            return
        
        # 计算当前页范围
        start_idx = self.current_page * self.per_page
        end_idx = min((self.current_page + 1) * self.per_page, len(self.wafer_data))
        current_data = self.wafer_data[start_idx:end_idx]
        
        # 创建箱型图
        ax = self.figure.add_subplot(111)
        
        # ==== 绘制红色的目标线 ====
        if self.target_value is not None:
            # 使用axhline绘制水平线
            ax.axhline(y=self.target_value, color='red', linestyle='--', linewidth=2)
            
            # 添加图例
            ax.legend([f'目标厚度: {self.target_value:.2f} nm'], 
                      loc='upper right', frameon=True, framealpha=0.7)
        
        # 准备数据用于绘图
        thickness_data = []
        labels = []
        for data, filename, _ in current_data:
            if data is not None and len(data) > 0:
                # 去掉文件名后缀并截断过长的文件名
                clean_filename = os.path.splitext(filename)[0][:20]
                labels.append(clean_filename)
                thickness_data.append(data[:, 2])  # 厚度数据在第三列
        
        # 检查是否有效数据
        if not thickness_data:
            ax.text(0.5, 0.5, '当前页没有有效数据', 
                    ha='center', va='center', fontsize=12)
            ax.axis('off')
            self.canvas.draw()
            return
            
        # 创建箱型图
        boxplot = ax.boxplot(thickness_data, 
                             patch_artist=True, 
                             showmeans=True, 
                             meanline=True,
                             labels=labels)
        
        # 设置箱型图颜色
        colors = ['#3498db', '#e74c3c', '#2ecc71', '#f1c40f', '#9b59b6',
                 '#1abc9c', '#d35400', '#34495e', '#7f8c8d', '#8e44ad']
        for patch, color in zip(boxplot['boxes'], colors * (len(thickness_data)//10 + 1)):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
            
        # 设置均值线属性
        plt.setp(boxplot['means'], linestyle='-', color='black', linewidth=1.2)
        plt.setp(boxplot['medians'], linestyle='-', color='darkorange', linewidth=1.5)
        
        # 添加网格和标题
        ax.grid(True, linestyle='--', alpha=0.3)
        
        # 更新标题，包含目标值信息
        title = f'晶圆膜厚分布统计 - 第 {self.current_page+1}/{self.total_pages} 页'
        
        if self.target_value is not None:
            title += f' (目标值: {self.target_value:.2f} nm)'
        
        ax.set_title(title, fontsize=14)
        
        ax.set_ylabel('膜厚 (nm)', fontsize=10)
        ax.set_xlabel('晶圆名称', fontsize=10)
        
        # 旋转x轴标签避免重叠
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right', fontsize=8)
        
        # 调整布局
        self.figure.tight_layout()
        self.canvas.draw()
        
        # 更新页面标签
        self.page_label.setText(f"页面: {self.current_page+1}/{self.total_pages}")
        
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.draw_boxplots()
    
    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.draw_boxplots()

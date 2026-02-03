# distribution_dialog.py
import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QDialogButtonBox, QSizePolicy
)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy.stats import norm
import matplotlib.pyplot as plt
import sys

class DistributionDialog(QDialog):
    def __init__(self, thickness_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("厚度分布统计")
        self.setMinimumSize(800, 600)
        self.thickness_data = thickness_data
        self.current_bin_size = None
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 控制面板
        control_layout = QHBoxLayout()
        
        self.bin_size_label = QLabel("直方图组距 (nm):")
        control_layout.addWidget(self.bin_size_label)
        
        self.bin_size_entry = QLineEdit()
        self.bin_size_entry.setFixedWidth(100)
        self.bin_size_entry.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        control_layout.addWidget(self.bin_size_entry)
        
        self.update_button = QPushButton("更新图表")
        self.update_button.clicked.connect(self.update_histogram)
        control_layout.addWidget(self.update_button)
        
        control_layout.addStretch(1)
        
        # 添加关闭按钮
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)
        control_layout.addWidget(self.close_button)
        
        layout.addLayout(control_layout)
        
        # 创建图表控件
        self.figure = Figure(figsize=(8, 6))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # 初始绘图
        self.draw_distribution_stats()
        
        # 设置初始焦点
        self.bin_size_entry.setFocus()
    
    def draw_distribution_stats(self):
        """绘制统计图表"""
        self.figure.clear()
        
        if self.thickness_data is None or len(self.thickness_data) < 3:
            # 没有数据的情况
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, '至少需要3个数据点才能生成分布统计', 
                    horizontalalignment='center', verticalalignment='center',
                    fontsize=12, color='red')
            ax.axis('off')
            self.canvas.draw()
            return
        
        try:
            # 计算统计信息
            thickness = self.thickness_data
            mu = np.mean(thickness)
            sigma = np.std(thickness)
            min_val = np.min(thickness)
            max_val = np.max(thickness)
            
            # 获取或计算组距
            bin_text = self.bin_size_entry.text().strip()
            if bin_text:
                try:
                    bin_size = float(bin_text)
                    if bin_size <= 0:
                        raise ValueError
                except ValueError:
                    bin_size = None
            else:
                bin_size = None
            
            if bin_size is None:
                # 自动计算组距 (Freedman-Diaconis规则)
                q75, q25 = np.percentile(thickness, [75, 25])
                iqr = q75 - q25
                bin_size = 2 * iqr / (len(thickness) ** (1/3)) if iqr > 0 else (max_val - min_val)/10
                bin_size = max(bin_size, (max_val - min_val)/20)
                self.bin_size_entry.setText(f"{bin_size:.3f}")
            
            bins = np.arange(min_val, max_val + bin_size, bin_size)
            
            # 创建直方图
            ax1 = self.figure.add_subplot(211)
            n, bins, patches = ax1.hist(
                thickness, bins=bins, 
                density=True, edgecolor='black', 
                alpha=0.7
            )
            
            # 计算累积分布
            cumulative = np.cumsum(n) * bin_size
            
            # 添加累积分布曲线
            ax2 = ax1.twinx()
            ax2.plot(
                bins[:-1], cumulative, 
                color='orange', 
                linestyle='--', 
                linewidth=2,
                marker='o',
                markersize=4
            )
            ax2.set_ylabel('累积概率', rotation=270, labelpad=20)
            
            # 设置直方图属性
            ax1.set_title(f"厚度分布直方图 (组距={bin_size:.3f}nm)")
            ax1.set_xlabel("厚度 (nm)")
            ax1.set_ylabel("频率密度")
            ax1.grid(True, linestyle='--', alpha=0.3)
            
            # 创建正态分布拟合
            ax3 = self.figure.add_subplot(212)
            
            # 生成正态分布曲线
            x_min = mu - 4 * sigma
            x_max = mu + 4 * sigma
            if x_min < min_val:
                x_min = min_val
            if x_max > max_val:
                x_max = max_val
                
            x = np.linspace(x_min, x_max, 300)
            pdf = norm.pdf(x, mu, sigma)
            
            ax3.plot(x, pdf, 'r-', linewidth=2)
            ax3.fill_between(x, pdf, 0, alpha=0.3, color='red')
            
            # 添加实测数据密度分布
            try:
                from scipy.stats import gaussian_kde
                kde = gaussian_kde(thickness)
                ax3.plot(x, kde(x), 'b--', linewidth=1.5, label="实测分布")
            except Exception as e:
                print(f"无法计算KDE: {str(e)}")
            
            # 设置正态图属性
            ax3.set_title("正态分布拟合曲线")
            ax3.set_xlabel("厚度 (nm)")
            ax3.set_ylabel("概率密度")
            ax3.grid(True, linestyle='--', alpha=0.3)
            ax3.legend()
            
            # 添加统计信息文字
            stats_text = (
                f"数据点数: {len(thickness)}\n"
                f"平均值 (μ): {mu:.3f} nm\n"
                f"标准差 (σ): {sigma:.3f} nm\n"
                f"最小值: {min_val:.3f} nm\n"
                f"最大值: {max_val:.3f} nm"
            )
            ax3.text(
                0.98, 0.65, stats_text,
                transform=ax3.transAxes,
                verticalalignment='top',
                horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                fontsize=10
            )
            
            self.figure.tight_layout()
            self.canvas.draw()
            self.current_bin_size = bin_size
            
        except Exception as e:
            self.show_error(f"图表生成错误: {str(e)}")
    
    def update_histogram(self):
        """更新直方图"""
        self.draw_distribution_stats()
    
    def show_error(self, message):
        """显示错误消息"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, message, 
                horizontalalignment='center', verticalalignment='center',
                fontsize=12, color='red')
        ax.axis('off')
        self.canvas.draw()

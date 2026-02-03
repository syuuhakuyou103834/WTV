import numpy as np
from PyQt5.QtWidgets import QSizePolicy
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.cm import get_cmap
from matplotlib.colors import Normalize
from matplotlib.patches import Circle
from matplotlib import ticker

class PlotPanel(FigureCanvas):
    def __init__(self, parent=None):
        super().__init__(Figure())
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 设置图形属性
        self.figure.set_facecolor('#f9f9f9')
        self.figure.set_dpi(100)
        
        # 创建图表轴对象
        self.ax = self.figure.add_subplot(111)
        self.ax.grid(True, linestyle='--', linewidth=0.7, alpha=0.7)
        self.ax.set_axisbelow(True)  # 网格在数据下方
        self.ax.axis('equal')        # 确保比例相等
        
        # 变量初始化
        self.scatter = None
        self.highlight_color = np.array([1.0, 0.0, 0.0, 1.0])    # 红色高亮 (RGBA)
        self.default_edge_color = np.array([0.7, 0.7, 0.7, 1.0]) # 默认边缘颜色 (RGBA)
        self.last_edge_colors = None
        self.last_hover_index = -1
        self.colorbar = None
    
    def draw_wafer(self, data, wafer_size=200, extend_edge=False, 
                  custom_range=None, show_scatter=True):
        """绘制晶圆分布图
        Args:
            data (ndarray): N×3的数组，包含(X, Y, Thickness)
            wafer_size (float): 晶圆直径(mm)
            extend_edge (bool): 是否扩展边缘点
            custom_range (dict): 可选的颜色范围 {'min': float, 'max': float}
            show_scatter (bool): 是否显示散点
        """

        try:
            # 清除现有内容
            self.ax.clear()
            self.ax.grid(True, linestyle='--', linewidth=0.7, alpha=0.7)
            self.ax.set_axisbelow(True)
            self.ax.axis('equal')
            
            # 设置范围时考虑扩展边缘的情况
            if extend_edge:
                scale = wafer_size * 1.1 / 2  # 10%的余量
            else:
                scale = wafer_size * 1.05 / 2  # 5%的余量
            
            self.ax.set_xlim([-scale, scale])
            self.ax.set_ylim([-scale, scale])
            
            # 移除之前的colorbar
            if self.colorbar:
                self.colorbar.remove()
                self.colorbar = None
            
            # 添加晶圆轮廓
            wafer_circle = Circle(
                (0, 0), wafer_size/2, 
                edgecolor="black", 
                fill=False, 
                linestyle='-',
                linewidth=1.5,
                zorder=0
            )
            self.ax.add_patch(wafer_circle)
            self.ax.set_title("WF膜厚分布图", fontsize=12, pad=10)
            
            # 设置轴标签
            self.ax.set_xlabel("晶圆坐标 (mm)", fontsize=9, labelpad=8)
            self.ax.set_ylabel("晶圆坐标 (mm)", fontsize=9, labelpad=8)
            self.ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
            
            # 绘制散点图
            x, y, thickness = data[:, 0], data[:, 1], data[:, 2]
            
            # 设定颜色范围
            if custom_range and 'min' in custom_range and 'max' in custom_range:
                vmin = custom_range['min']
                vmax = custom_range['max']
            else:
                vmin = np.min(thickness)
                vmax = np.max(thickness)
                
            norm = Normalize(vmin=vmin, vmax=vmax)
            cmap = get_cmap('viridis')
            
            # 绘制散点图
            scatter = self.ax.scatter(
                x, y, 
                c=thickness, 
                cmap=cmap,
                norm=norm,
                s=35, 
                alpha=0.75,
                edgecolors=self.default_edge_color,
                linewidths=0.7
            )
            
            # 激活散点可见性
            self.scatter = scatter
            self.scatter.set_visible(show_scatter)
            
            # 保存默认边缘颜色
            if self.scatter:
                point_count = len(thickness)
                self.last_edge_colors = np.tile(self.default_edge_color, (point_count, 1))
            
            # 添加colorbar
            cax = self.figure.add_axes([0.92, 0.12, 0.02, 0.75])
            self.colorbar = self.figure.colorbar(
                scatter, cax=cax, orientation='vertical', 
                format="%.1f", label='厚度 (nm)'
            )
            
            # 设置colorbar刻度标签字体
            cax.minorticks_on()
            cax.tick_params(axis='y', labelsize=8)
            
            # 更新图表
            self.draw_idle()
            return True
        except Exception as e:
            print(f">>> 绘图错误: {str(e)}")
            return False
    
    def update_plot(self):
        """重新绘制当前图表状态"""
        self.draw_idle()
        
    def highlight_point(self, index):
        """高亮显示指定索引的数据点"""
        if self.scatter is None or self.last_edge_colors is None:
            return
            
        colors = np.array(self.scatter.get_edgecolors())
        
        # 恢复上一个高亮点
        if self.last_hover_index >= 0 and self.last_hover_index < len(colors):
            colors[self.last_hover_index] = self.last_edge_colors[self.last_hover_index]
        
        # 设置新的高亮点
        if index >= 0 and index < len(colors):
            colors[index] = self.highlight_color
            self.last_hover_index = index
        else:
            self.last_hover_index = -1
        
        self.scatter.set_edgecolors(colors)
        self.draw_idle()
    
    def highlight_selected(self, indices):
        """高亮显示一组选中的数据点"""
        if self.scatter is None or self.last_edge_colors is None:
            return
            
        colors = np.array(self.scatter.get_edgecolors())
        
        # 重置所有高亮
        colors = np.array(self.last_edge_colors)
        
        # 为选中的点设置高亮颜色
        for idx in indices:
            if 0 <= idx < len(colors):
                colors[idx] = self.highlight_color
        
        self.scatter.set_edgecolors(colors)
        self.draw_idle()

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from scipy.interpolate import griddata, RBFInterpolator
from scipy.spatial import cKDTree
import os
import sys

def create_wafer_figure():
    fig = Figure(figsize=(8, 7))
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    return fig, ax

def draw_wafer_map(fig, ax, data, wafer_size, extend_edge, custom_range=None, show_scatter=True):
    if data is None or len(data) < 3:
        return fig
    
    # 确保清除之前的绘图和颜色条
    ax.clear()
    
    # --- 关键修复: 清除现有的colorbar ---
    # 检查并移除所有现有colorbar（过滤子图坐标轴）
    for cb in fig.get_axes():
        if isinstance(cb, type(fig.axes[0])) and cb is not ax:
            cb.remove()
    
    # 提取数据
    x, y, z = data.T
    wafer_radius = wafer_size / 2
    
    # 高效插值计算
    if extend_edge:
        # 使用RBF插值获得更平滑的曲面
        try:
            rbf = RBFInterpolator(
                np.column_stack([x, y]),
                z,
                kernel='thin_plate_spline',
                smoothing=0.1  # 添加平滑参数防止过拟合
            )
            # 创建密集网格
            grid_x, grid_y = np.meshgrid(
                np.linspace(-wafer_radius, wafer_radius, 300),
                np.linspace(-wafer_radius, wafer_radius, 300)
            )
            grid_z = rbf(np.column_stack([grid_x.ravel(), grid_y.ravel()]))
            grid_z = grid_z.reshape(grid_x.shape)
        except Exception as e:
            print(f"RBF插值失败: {e}，回退到线性插值")
            grid_x, grid_y, grid_z = grid_data_with_fallback(x, y, z, wafer_radius, extend_edge)
    else:
        grid_x, grid_y, grid_z = grid_data_with_fallback(x, y, z, wafer_radius, extend_edge)
    
    # 应用晶圆边界掩码
    distance = np.sqrt(grid_x**2 + grid_y**2)
    grid_z[distance > wafer_radius] = np.nan

    # 绘制等高线图
    vmin, vmax = (None, None)
    if custom_range and any([custom_range['min'], custom_range['max']]):
        vmin = custom_range['min']
        vmax = custom_range['max']
    
    contour = ax.contourf(
        grid_x, grid_y, grid_z, 
        levels=50,
        cmap='jet',
        extend='both' if (vmin or vmax) else 'neither',
        vmin=vmin,
        vmax=vmax
    )
    
    # --- 关键修复: 在原来位置创建新的colorbar ---
    # 注意: position参数确保每次都创建在同一位置
    cax = fig.add_axes([0.92, 0.15, 0.02, 0.7])  # [左, 下, 宽, 高]
    cbar = fig.colorbar(contour, cax=cax, label='厚度 (nm)')
    
    # 绘制晶圆边界
    wafer = Circle((0,0), wafer_radius, edgecolor='gray', fill=False, linewidth=2)
    ax.add_patch(wafer)
    
    # 为边缘扩展模式添加虚线边界
    if extend_edge:
        ax.add_patch(Circle(
            (0,0), wafer_radius, 
            edgecolor='darkred', fill=False, 
            linewidth=2, linestyle='--', 
            zorder=15)
        )
    
    # 绘制数据点 - 使用z值着色
    scatter_artist = ax.scatter(
        x, y, c=z, s=40, cmap='jet', 
        edgecolors=(0.7, 0.7, 0.7, 1), 
        alpha=0.9, 
        vmin=vmin, 
        vmax=vmax, 
        visible=show_scatter, 
        zorder=10,
        picker=True,  # 启用点选
        pickradius=5   # 选择半径（像素）
    )
    
    # 设置轴属性
    if extend_edge:
        ax.set_title("扩展边界: 晶圆厚度分布图")
        # 固定显示整个晶圆
        display_radius = wafer_radius * 1.05
        ax.set_xlim(-display_radius, display_radius)
        ax.set_ylim(-display_radius, display_radius)
    else:
        ax.set_title("晶圆厚度分布图")
        # 自适应数据范围
        x_margin = (np.max(x) - np.min(x)) * 0.1
        y_margin = (np.max(y) - np.min(y)) * 0.1
        ax.set_xlim(np.min(x) - x_margin, np.max(x) + x_margin)
        ax.set_ylim(np.min(y) - y_margin, np.max(y) + y_margin)
    
    ax.set_xlabel("X 坐标 (mm)")
    ax.set_ylabel("Y 坐标 (mm)")
    ax.set_aspect('equal')
    ax.grid(False)  # 提高对比度
    
    return fig, scatter_artist

def grid_data_with_fallback(x, y, z, wafer_radius, extend_edge):
    """使用不同插值方法的数据网格生成（带失败回退）"""
    # 计算数据边界
    if extend_edge:
        x_min = -wafer_radius
        x_max = wafer_radius
        y_min = -wafer_radius
        y_max = wafer_radius
    else:
        x_min, x_max = np.min(x), np.max(x)
        y_min, y_max = np.min(y), np.max(y)
        
        # 适当地扩展到晶圆边界
        max_extent = max(
            wafer_radius,
            (x_max - x_min) / 2,
            (y_max - y_min) / 2
        )
        x_center, y_center = (np.mean([x_min, x_max]), np.mean([y_min, y_max]))
        x_min = min(x_center - max_extent, -wafer_radius)
        x_max = max(x_center + max_extent, wafer_radius)
        y_min = min(y_center - max_extent, -wafer_radius)
        y_max = max(y_center + max_extent, wafer_radius)
    
    # 创建网格
    grid_x, grid_y = np.meshgrid(
        np.linspace(x_min, x_max, 200),
        np.linspace(y_min, y_max, 200)
    )
    
    # 尝试不同插值方法
    try:
        grid_z = griddata((x, y), z, (grid_x, grid_y), method='cubic')
    except:
        try:
            grid_z = griddata((x, y), z, (grid_x, grid_y), method='linear')
        except:
            grid_z = griddata((x, y), z, (grid_x, grid_y), method='nearest')
    
    # 应用圆形边界
    distance = np.sqrt(grid_x**2 + grid_y**2)
    grid_z[distance > wafer_radius] = np.nan
    
    return grid_x, grid_y, grid_z

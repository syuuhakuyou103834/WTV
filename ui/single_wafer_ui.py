import os
import numpy as np
import time
import traceback
from PyQt5.QtWidgets import (
    QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QLabel, QMessageBox, QSizePolicy, QFileDialog, 
    QDialog, QMenu, QLineEdit, QDialogButtonBox, QInputDialog,QProgressDialog, QApplication
)
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QCursor
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from scipy.interpolate import griddata, RBFInterpolator
from scipy.spatial import cKDTree
from matplotlib.patches import Circle

# 导入自定义模块
from ui.dialogs import DataInputDialog, RangeSelectDialog, PostSelectDialog
from ui.panels import ControlPanel
from ui.distribution_dialog import DistributionDialog
from core.data_processing import add_data_point as dp_add_point, delete_points, load_wafer_data, calculate_statistics
from utils.file_io import open_file_dialog, save_file_dialog, export_data
from utils.config import config
from ui.dialogs import NewGridSettingsDialog  # 导入新对话框


class SingleWaferUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        
        # 初始化数据状态
        self.raw_data = None
        self.current_data = None
        self.selected_indices = []
        self.custom_vmin = None
        self.custom_vmax = None
        self.show_scatter = True
        self.wafer_size = 150  # 默认尺寸
        self.extend_edge = False
        self.filename = "未加载文件"
        self.current_file_path = None  # 存储当前文件路径
        self.kd_tree = None
        self.stats_dialog = None
        
        # 高亮状态跟踪
        self.last_hover_index = -1  # 最后悬停的点索引
        self.edge_colors = None    # 所有点的边缘颜色数组
        
        # 初始化UI组件
        self.init_ui()
        self.bind_events()

        #初始化缓存变量
        self.interpolation_grid = None  # 缓存插值网格
        self.rbf_interpolator = None    # RBF插值器缓存
        self.last_interpolation_method = None
    
    def init_ui(self):
        # 创建主布局
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建分隔器
        splitter = QSplitter(Qt.Horizontal)
        
        # 创建控制面板
        self.control_panel = ControlPanel(self)
        splitter.addWidget(self.control_panel)
        splitter.setCollapsible(0, False)
        
        # 创建绘图面板容器
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建绘图面板
        self.figure = Figure(figsize=(8, 7))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_layout.addWidget(self.canvas)
        
        # 信息标签
        self.file_label = QLabel(f"当前文件: {self.filename}")
        self.file_label.setAlignment(Qt.AlignCenter)
        
        self.size_label = QLabel(f"晶圆尺寸: {self.wafer_size} mm")
        self.size_label.setAlignment(Qt.AlignCenter)
        
        self.hover_info_label = QLabel("悬停显示数据点信息")
        self.hover_info_label.setAlignment(Qt.AlignCenter)
        
        plot_layout.addWidget(self.file_label)
        plot_layout.addWidget(self.size_label)
        plot_layout.addWidget(self.hover_info_label)
        
        splitter.addWidget(plot_container)
        splitter.setCollapsible(1, False)
        
        # 将分隔器添加到主布局
        main_layout.addWidget(splitter)
        
        # 设置分隔器初始比例
        splitter.setSizes([300, 800])
        
        # 初始化绘图区域
        self.init_plot()
    
    def init_plot(self):
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("晶圆厚度分布图", fontsize=12)
        self.ax.set_xlabel("X 坐标 (mm)", fontsize=9)
        self.ax.set_ylabel("Y 坐标 (mm)", fontsize=9)
        self.canvas.draw()
    
    def set_wafer_size(self, size):
        """设置晶圆尺寸并更新显示"""
        self.wafer_size = size
        self.size_label.setText(f"晶圆尺寸: {self.wafer_size} mm")
        
        # 如果已经有数据，重新绘制
        if self.current_data is not None:
            self.redraw_plot()
    
    def bind_events(self):
        self.canvas.mpl_connect('motion_notify_event', self.on_hover)
        self.canvas.mpl_connect('button_press_event', self.on_click)
        
        # 连接控制面板的信号
        if self.control_panel:
            self.control_panel.apply_btn.clicked.connect(self.apply_color_scale)
            self.control_panel.auto_btn.clicked.connect(self.auto_color_scale)
            self.control_panel.extend_cb.toggled.connect(self.toggle_boundary)
            self.control_panel.points_cb.toggled.connect(self.toggle_scatter_visibility)
            self.control_panel.add_point_btn.clicked.connect(self.add_data_point)
    
    def calculate_data_bounds(self):
        """计算数据边界"""
        if self.current_data is None or len(self.current_data) == 0:
            return -5, 5, -5, 5
        
        x_data = self.current_data[:,0]
        y_data =self.current_data[:,1]
        
        x_range = x_data.max() - x_data.min()
        y_range = y_data.max() - y_data.min()
        
        x_padding = x_range * 0.05 if x_range > 0 else 1.0
        y_padding = y_range * 0.05 if y_range > 0 else 1.0
        
        return (
            x_data.min() - x_padding,
            x_data.max() + x_padding,
            y_data.min() - y_padding,
            y_data.max() + y_padding
        )
    
    def redraw_plot(self):
        """重绘晶圆图像"""
        if self.current_data is None or len(self.current_data) < 3:
            return
            
        try:
            # 清除之前内容
            self.figure.clear()
            self.ax = self.figure.add_subplot(111)
            
            title = f"{self.wafer_size}mm 晶圆厚度分布图"
            if self.filename and self.filename != "未加载文件":
                title += f" - {self.filename}"
            self.ax.set_title(title, fontsize=12)
            
            self.ax.set_xlabel("X 坐标 (mm)", fontsize=9)
            self.ax.set_ylabel("Y 坐标 (mm)", fontsize=9)
            
            # 提取数据
            x, y, z = self.current_data.T
            
            # 计算网格
            if self.extend_edge:
                # 扩展模式强制使用全范围
                scale = self.wafer_size * 1.1 / 2
                x_min = -scale
                x_max = scale
                y_min = -scale
                y_max = scale
            else:
                x_min, x_max, y_min, y_max = self.calculate_data_bounds()
            
            grid_x, grid_y = np.meshgrid(
                np.linspace(x_min, x_max, 200),
                np.linspace(y_min, y_max, 200)
            )
            
            # 插值方法选择
            if self.extend_edge:
                try:
                    # RBF插值
                    rbf = RBFInterpolator(
                        np.column_stack([x, y]),
                        z,
                        kernel='thin_plate_spline',
                        neighbors=min(200, len(x)-1)
                    )
                    grid_z = rbf(np.column_stack([grid_x.ravel(), grid_y.ravel()])).reshape(grid_x.shape)
                except Exception as e:
                    print(f"RBF 插值失败: {e}，回退到线性插值")
                    grid_z = griddata((x, y), z, (grid_x, grid_y), method='linear')
            else:
                for method in ['cubic', 'linear', 'nearest']:
                    try:
                        grid_z = griddata((x, y), z, (grid_x, grid_y), method=method)
                        break
                    except:
                        continue
            
            # 晶圆边缘处理
            wafer_radius = self.wafer_size / 2
            distance = np.sqrt(grid_x**2 + grid_y**2)
            grid_z[distance > wafer_radius] = np.nan
            
            # 处理自定义颜色范围
            vmin, vmax = None, None
            if self.custom_vmin is not None and self.custom_vmax is not None:
                vmin = self.custom_vmin
                vmax = self.custom_vmax
            else:
                vmin = np.nanmin(grid_z)
                vmax = np.nanmax(grid_z)
            
            # 绘制等高线图
            contour = self.ax.contourf(grid_x, grid_y, grid_z, levels=50,
                                     cmap='jet', vmin=vmin, vmax=vmax)
            
            # 添加颜色条
            cbar = self.figure.colorbar(contour, ax=self.ax)
            cbar.set_label('厚度 (nm)')
            
            # 添加晶圆轮廓
            wafer = Circle((0, 0), wafer_radius, edgecolor='gray', fill=False, linewidth=1.5)
            self.ax.add_patch(wafer)
            
            # 绘制散点
            self.scatter = self.ax.scatter(x, y, c=z, s=35, edgecolors='gray', 
                                         cmap='jet', vmin=vmin, vmax=vmax, 
                                         alpha=0.7, zorder=10)
            self.scatter.set_visible(self.show_scatter)
            
            # 初始化边缘颜色数组
            n_points = len(self.current_data)
            self.edge_colors = np.full((n_points, 4), [0.7, 0.7, 0.7, 1])  # 默认为灰色
            self.scatter.set_edgecolors(self.edge_colors)
            
            # 设置比例相等并调整视图
            self.ax.set_aspect('equal')
            self.ax.grid(True, linestyle='--', alpha=0.5)
            
            # 设置坐标轴范围
            if self.extend_edge:
                self.ax.set_xlim(-wafer_radius * 1.1, wafer_radius * 1.1)
                self.ax.set_ylim(-wafer_radius * 1.1, wafer_radius * 1.1)
            else:
                margin = 0
                self.ax.set_xlim(x_min - margin, x_max + margin)
                self.ax.set_ylim(y_min - margin, y_max + margin)
            
            # 重建KD树
            self.kd_tree = cKDTree(self.current_data[:, :2])
            
            # 更新统计信息
            stats = calculate_statistics(self.current_data)
            self.control_panel.update_stats(stats)
            
            # 高亮当前选中的点
            if self.selected_indices:
                self.highlight_selected_points()
            
            # 刷新画布
            self.canvas.draw()
            
            # 更新状态
            self.update_status_message("绘图已完成")
            
        except Exception as e:
            err_msg = f"绘图错误: {str(e)}"
            self.update_status_message(err_msg, "error")
            QMessageBox.critical(self, "错误", err_msg)
            traceback.print_exc()
    
    def load_data(self):
        """加载晶圆数据文件"""
        result = open_file_dialog("选择数据文件", self, "数据文件 (*.csv *.txt);;所有文件 (*.*)")
        if not result or not result[0]:
            return
        
        file_path = result[0]
        
        # 询问晶圆尺寸
        size, ok = QInputDialog.getItem(
            self, 
            "设置晶圆尺寸", 
            "请选择晶圆尺寸:", 
            ["100", "150", "200", "300"], 
            1,  # 默认选择150
            False
        )
        
        if not ok:
            return
            
        try:
            wafer_size = int(size)
            self.set_wafer_size(wafer_size)
        except ValueError:
            self.set_wafer_size(150)  # 默认值
        
        self.load_file(file_path)
    
    def load_file(self, file_path):
        """从文件路径加载数据"""
        try:
            data, filename_part = load_wafer_data(file_path)
            self.raw_data = data
            self.current_data = self.raw_data.copy()
            self.filename = filename_part
            self.current_file_path = file_path
            self.file_label.setText(f"当前文件: {self.filename}")
            self.update_status_message(f"已加载文件: {self.filename}")
            self.redraw_plot()
        except Exception as e:
            err_msg = f"文件读取失败: {str(e)}"
            self.update_status_message(err_msg, "error")
            QMessageBox.critical(self, "错误", err_msg)
            traceback.print_exc()

    def load_file_directly(self, file_path, wafer_size):
        """直接从文件路径加载数据（用于从批量视图切换）"""
        try:
            # 设置晶圆尺寸
            self.set_wafer_size(wafer_size)
            
            # 加载文件
            self.load_file(file_path)
            
            # 通知批量处理视图准备更新
            if self.parent_window and hasattr(self.parent_window, 'batch_wafer_tab'):
                self.parent_window.batch_wafer_tab.prepare_for_update(file_path, self.current_data)
        except Exception as e:
            err_msg = f"文件读取失败: {str(e)}"
            self.update_status_message(err_msg, "error")
            traceback.print_exc()
    
    def add_data_point(self):
        """手动添加数据点"""
        dlg = DataInputDialog(parent=self, default_wafer_size=self.wafer_size)
        if dlg.exec_() == QDialog.Accepted and dlg.result:
            try:
                x, y, thickness = dlg.result
                valid = True
                
                # 验证值
                max_range = self.wafer_size / 2
                if abs(x) > max_range or abs(y) > max_range:
                    valid = False
                    err = f"坐标必须在直径{self.wafer_size}mm的范围内"
                elif thickness <= 0:
                    valid = False
                    err = "膜厚值必须大于0"
                
                if not valid:
                    QMessageBox.warning(self, "输入错误", err)
                    return
                
                # 添加数据点
                new_point = np.array([x, y, thickness])
                self.current_data = dp_add_point(self.current_data, new_point, self.wafer_size)
                
                if self.raw_data is None:
                    self.raw_data = self.current_data.copy()
                    
                self.update_status_message("已添加/更新数据点")
                self.redraw_plot()
            except Exception as e:
                err_msg = f"添加数据点时出错: {str(e)}"
                self.update_status_message(err_msg, "error")
                QMessageBox.critical(self, "错误", err_msg)
    
    def edit_thickness(self):
        """批量编辑选中点的厚度值"""
        if not self.selected_indices:
            return
            
        try:
            # 获取当前厚度值供用户参考
            thickness_values = self.current_data[self.selected_indices, 2]
            count = len(thickness_values)
            
            dlg = QDialog(self)
            dlg.setWindowTitle("修改厚度")
            dlg.setMinimumWidth(300)
            layout = QVBoxLayout(dlg)
            
            # 显示当前数据信息
            layout.addWidget(QLabel(f"已选择 {count} 个点"))
            min_val = np.min(thickness_values)
            max_val = np.max(thickness_values)
            avg_val = np.mean(thickness_values)
            layout.addWidget(QLabel(f"厚度范围: {min_val:.3f} - {max_val:.3f} nm"))
            layout.addWidget(QLabel(f"厚度均值: {avg_val:.3f} nm"))
            
            # 厚度输入框
            layout.addWidget(QLabel("\n新厚度 (nm):"))
            thickness_input = QLineEdit()
            thickness_input.setPlaceholderText("输入所有点的新厚度")
            layout.addWidget(thickness_input)
            
            # 操作按钮
            button_box = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel
            )
            button_box.accepted.connect(dlg.accept)
            button_box.rejected.connect(dlg.reject)
            layout.addWidget(button_box)
            
            if dlg.exec_() == QDialog.Accepted:
                new_thick = thickness_input.text().strip()
                if not new_thick:
                    QMessageBox.warning(self, "输入错误", "请输入厚度值")
                    return
                
                try:
                    new_thickness = float(new_thick)
                    # 有效值校验
                    if new_thickness <= 0:
                        QMessageBox.warning(self, "输入错误", "厚度必须大于0")
                        return
                    
                    # 修改所有选中点的厚度
                    self.current_data[self.selected_indices, 2] = new_thickness
                    
                    self.redraw_plot()
                    self.update_status_message(f"已更新 {count} 个点的厚度值")
                except ValueError:
                    QMessageBox.warning(self, "格式错误", "请输入有效的数字值")
        except Exception as e:
            QMessageBox.critical(self, "操作失败", f"厚度修改过程中出错: {str(e)}")
    
    def delete_point(self):
        """删除选中数据点"""
        if not self.selected_indices:
            return
            
        count = len(self.selected_indices)
        confirm = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {count} 个数据点吗?",
            QMessageBox.Yes | QMessageBox.No,
        )
        
        if confirm == QMessageBox.Yes:
            self.current_data = delete_points(self.current_data, self.selected_indices)
            self.selected_indices = []
            
            # 确保保留至少三个点
            if self.current_data is not None and len(self.current_data) >= 3:
                self.redraw_plot()
                self.update_status_message(f"已删除 {count} 个数据点")
            else:
                msg = "需要至少3个点才能继续可视化，已恢复原始数据"
                self.current_data = self.raw_data.copy() if self.raw_data is not None else None
                self.redraw_plot()
                QMessageBox.warning(self, "操作中止", msg)
    
    def on_hover(self, event):
        """处理鼠标悬停事件 - 改进版"""
        if (self.current_data is None or event.inaxes != self.ax or 
            not hasattr(self, 'scatter') or self.scatter is None or
            self.edge_colors is None):
            self.hover_info_label.setText("悬停显示数据点信息")
            return
            
        try:
            # 查找最近的数据点
            x, y = event.xdata, event.ydata
            dist, idx = self.kd_tree.query([x, y])
            
            # 计算悬停阈值 - 基于晶圆大小动态计算
            hover_threshold = self.wafer_size * 0.05  # 约5%晶圆直径
            
            # 如果鼠标在阈值范围外
            if dist > hover_threshold:
                # 取消之前悬停点的高亮
                if self.last_hover_index != -1:
                    # 如果点不是选中的，恢复为默认颜色
                    if self.last_hover_index not in self.selected_indices:
                        self.edge_colors[self.last_hover_index] = [0.7, 0.7, 0.7, 1]
                    
                    # 如果点是选中的，恢复为选中颜色
                    elif self.last_hover_index in self.selected_indices:
                        self.edge_colors[self.last_hover_index] = [1, 0, 0, 1]
                        
                    self.scatter.set_edgecolors(self.edge_colors)
                    self.canvas.draw_idle()
                
                self.last_hover_index = -1
                self.hover_info_label.setText("悬停显示数据点信息")
                return
                
            # 显示点信息
            data = self.current_data[idx]
            info_text = (f"坐标: X={data[0]:.2f}mm, Y={data[1]:.2f}mm | 厚度={data[2]:.3f}nm")
            self.hover_info_label.setText(info_text)
            
            # 检查是否悬停点发生变化
            if idx != self.last_hover_index:
                # 恢复上次悬停点的颜色
                if self.last_hover_index != -1:
                    if self.last_hover_index in self.selected_indices:
                        # 如果之前的悬停点是被选中的，保留红色
                        edge_color = [1, 0, 0, 1]
                    else:
                        # 否则恢复默认颜色
                        edge_color = [0.7, 0.7, 0.7, 1]
                    
                    self.edge_colors[self.last_hover_index] = edge_color
                
                # 设置新悬停点为红色
                self.edge_colors[idx] = [1, 0, 0, 1]
                self.scatter.set_edgecolors(self.edge_colors)
                self.canvas.draw_idle()
                
                self.last_hover_index = idx
            
        except Exception as e:
            # 仅打印错误，不大幅影响用户体验
            print(f"悬停处理错误: {str(e)}")
    
    def on_click(self, event):
        """处理鼠标点击事件 - 改进版"""
        if self.current_data is None or event.inaxes != self.ax:
            return
            
        try:
            # 查找最近的数据点
            x, y = event.xdata, event.ydata
            dist, idx = self.kd_tree.query([x, y])
            
            click_threshold = self.wafer_size * 0.05
            ctrl_pressed = event.key == 'control'  # 获取修饰键状态
            
            if event.button == 1:  # 左键点击
                if dist <= click_threshold:
                    # 点击到点附近
                    if not ctrl_pressed:  # 没有按control键 - 单选
                        # 清除之前的选择（除了当前点）
                        new_selection = set([idx])
                        
                        # 更新选中点集合
                        if self.selected_indices == [idx]:
                            # 点击已选中的点 - 取消选择
                            self.selected_indices = []
                        else:
                            # 选择新点
                            self.selected_indices = [idx]
                    else:  # 按住了control键 - 多选
                        if idx in self.selected_indices:
                            # 已选中则移除
                            self.selected_indices.remove(idx)
                        else:
                            # 未选中则添加
                            self.selected_indices.append(idx)
                else:  # 点击空白区域取消选择
                    self.selected_indices = []
            
            elif event.button == 3:  # 右键点击
                # 若点击位置无点，显示空白区域菜单
                if dist > click_threshold:
                    self.selected_indices = []  # 清除当前选择
                    self.show_context_menu(event)
                    return
                
                # 若点击点不存在于选择列表中，将其添加为唯一选择
                if idx not in self.selected_indices:
                    self.selected_indices = [idx]
                
                # 显示点相关上下文菜单
                self.show_context_menu(event)
                
            # 更新高亮显示
            self.highlight_selected_points()
            
        except Exception as e:
            print(f"点击处理错误: {str(e)}")
    
    def highlight_selected_points(self):
        """高亮所有选中点为红色"""
        if not hasattr(self, 'scatter') or self.scatter is None or self.edge_colors is None:
            return
            
        # 重置所有边缘颜色为默认
        self.edge_colors[:, :] = [0.7, 0.7, 0.7, 1]
        
        # 高亮选中点
        for idx in self.selected_indices:
            if 0 <= idx < len(self.edge_colors):
                self.edge_colors[idx] = [1, 0, 0, 1]  # 红色
        
        # 如果当前有悬停点且不是选中点，将其也高亮
        if self.last_hover_index != -1 and self.last_hover_index not in self.selected_indices:
            self.edge_colors[self.last_hover_index] = [1, 0, 0, 1]  # 红色
        
        self.scatter.set_edgecolors(self.edge_colors)
        self.canvas.draw_idle()
    
    def show_context_menu(self, event):
        """显示上下文菜单"""
        # 获取鼠标在屏幕坐标的绝对位置
        abs_pos = self.canvas.mapToGlobal(QPoint(event.x, event.y))
        
        menu = QMenu(self)
        
        if not self.selected_indices:  # 空白区域菜单
            menu.addAction("添加新数据点", self.add_data_point)
            menu.addAction("加载数据文件", self.load_data)
            
            # 如果已经有数据，添加"导回批量处理"选项
            if self.current_file_path:
                menu.addSeparator()
                menu.addAction("导回至批量处理页面", self.export_to_batch)
        else:  # 点操作菜单
            count = len(self.selected_indices)
            thickness_values = self.current_data[self.selected_indices, 2]
            
            if count == 1:
                text = f"修改厚度 ({thickness_values[0]:.3f} nm)"
            else:
                avg_thickness = np.mean(thickness_values)
                text = f"批量修改厚度 ({count}点 | 平均 {avg_thickness:.3f} nm)"
                
            menu.addAction(text, self.edit_thickness)
            menu.addSeparator()
            menu.addAction(f"删除{'选中点' if count > 1 else '此点'}", self.delete_point)
            
            # 添加"导回批量处理"选项
            menu.addSeparator()
            menu.addAction("导回至批量处理页面", self.export_to_batch)
        
        # 显示菜单
        menu.exec_(abs_pos)
    
    def export_to_batch(self):
        """将当前数据导回批量处理视图"""
        if not self.current_file_path or self.current_data is None:
            QMessageBox.warning(self, "操作失败", "没有可导出的数据")
            return
            
        # 通知批量处理视图准备更新
        if self.parent_window and hasattr(self.parent_window, 'batch_wafer_tab'):
            self.parent_window.batch_wafer_tab.prepare_for_update(
                self.current_file_path, 
                self.current_data
            )
            
            # 显示成功消息
            filename = os.path.basename(self.current_file_path)
            QMessageBox.information(
                self, 
                "数据已提交", 
                f"'{filename}' 的数据已提交到批量处理视图\n"
                "请在批量处理视图中右键点击该晶圆并选择应用更新"
            )
        else:
            QMessageBox.warning(self, "操作失败", "无法访问批量处理视图")
    
    def select_by_thickness_range(self):
        """根据厚度范围选择数据点"""
        if self.current_data is None:
            return
            
        dlg = RangeSelectDialog(self)
        if dlg.exec_() != QDialog.Accepted or not dlg.result:
            return
            
        # 提取范围值
        min_thickness, max_thickness = dlg.result
        
        # 筛选在范围内的点
        thickness_values = self.current_data[:, 2]
        valid_idx = np.where(
            (thickness_values >= min_thickness) & 
            (thickness_values <= max_thickness)
        )[0]
        
        if len(valid_idx) == 0:
            QMessageBox.information(self, "结果", "没有数据点在指定范围内")
            return
        
        self.selected_indices = valid_idx.tolist()
        self.highlight_selected_points()
        
        # 询问后续操作
        action_dlg = PostSelectDialog(self, len(valid_idx))
        if action_dlg.exec_() == QDialog.Accepted:
            if action_dlg.choice == 'delete':
                self.delete_point()
            elif action_dlg.choice == 'modify':
                self.edit_thickness()
    
    def export_data(self):
        """导出当前数据到文件"""
        if self.current_data is None or len(self.current_data) < 3:
            QMessageBox.warning(self, "数据不足", "需要至少3个点才能导出数据")
            return
        
        # 打开保存对话框
        save_path = save_file_dialog(
            "导出数据",
            filter="数据文件 (*.csv *.xlsx);;CSV文件 (*.csv);;Excel文件 (*.xlsx)"
        )
        
        if not save_path:
            return
        
        try:
            export_data(self.current_data, save_path)
            QMessageBox.information(self, "导出成功", f"数据已保存到:\n{save_path}")
            self.update_status_message(f"已导出数据到: {os.path.basename(save_path)}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程中出错: {str(e)}")
    
    def export_image(self):
        """导出当前图像到文件"""
        if self.current_data is None or len(self.current_data) < 3:
            QMessageBox.warning(self, "数据不足", "需要至少3个点才能导出图像")
            return
        
        # 打开保存对话框
        save_path = save_file_dialog(
            "导出图像",
            filter="PNG图像 (*.png);;JPEG图像 (*.jpg);;PDF文档 (*.pdf);;所有文件 (*.*)"
        )
        
        if not save_path:
            return
        
        try:
            # 检查文件扩展名
            if not save_path.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
                save_path += '.png'
            
            # 保存图像
            self.figure.savefig(save_path, dpi=300, bbox_inches="tight")
            QMessageBox.information(self, "导出成功", f"图像已保存到:\n{save_path}")
            self.update_status_message(f"已导出图像: {os.path.basename(save_path)}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"保存图像时出错: {str(e)}")
    
    def apply_color_scale(self):
        """应用自定义的颜色范围设置"""
        vmin_text = self.control_panel.vmin_entry.text().strip()
        vmax_text = self.control_panel.vmax_entry.text().strip()
        
        try:
            vmin = float(vmin_text) if vmin_text else None
            vmax = float(vmax_text) if vmax_text else None
                
            # 验证范围有效性
            if vmin is not None and vmax is not None and vmin >= vmax:
                QMessageBox.warning(self, "范围错误", "最小值必须小于最大值")
                return
                
            self.custom_vmin = vmin
            self.custom_vmax = vmax
            self.redraw_plot()
            
        except ValueError:
            QMessageBox.warning(self, "格式错误", "请为颜色范围输入有效数字")
    
    def auto_color_scale(self):
        """重置为自动颜色范围设置"""
        self.custom_vmin = None
        self.custom_vmax = None
        self.control_panel.vmin_entry.clear()
        self.control_panel.vmax_entry.clear()
        self.redraw_plot()
    
    def toggle_boundary(self, checked):
        """切换边界扩展模式的显示"""
        self.extend_edge = checked
        self.redraw_plot()
        if checked:
            self.update_status_message("已启用边界点扩展")
        else:
            self.update_status_message("已禁用边界点扩展")
    
    def toggle_scatter_visibility(self, checked):
        """切换散点的显示/隐藏"""
        self.show_scatter = checked
        try:
            if hasattr(self, 'scatter') and self.scatter:
                self.scatter.set_visible(checked)
                self.canvas.draw_idle()
                
                if checked:
                    self.update_status_message("已显示数据点散点")
                else:
                    self.update_status_message("已隐藏数据点散点")
        except AttributeError:
            pass  # 没有散点

    def toggle_distribution_stats(self):
        """显示/隐藏厚度分布统计窗口"""
        if self.current_data is None or len(self.current_data) < 3:
            QMessageBox.warning(self, "数据不足", "需要至少3个数据点才能生成分布统计")
            return
        
        if hasattr(self, 'stats_dialog') and self.stats_dialog is not None:
            if self.stats_dialog.isVisible():
                self.stats_dialog.hide()
            else:
                self.stats_dialog.show()
                self.stats_dialog.activateWindow()
        else:
            thickness_data = self.current_data[:, 2]
            self.stats_dialog = DistributionDialog(thickness_data, self)
            self.stats_dialog.show()
    
    def update_status_message(self, message, level="info"):
        """更新状态栏消息"""
        if self.parent_window:
            self.parent_window.update_status_message(message, level)


    def setup_grid_interpolator(self):
        """设置当前数据的网格插值器并缓存结果"""
        if self.current_data is None or len(self.current_data) < 3:
            print("[DEBUG] 无法设置插值器: 数据不足")
            return None, None, None
            
        # 如果已经有缓存且数据未变化，直接返回缓存结果
        if (self.interpolation_grid is not None and 
            np.array_equal(self.cached_data, self.current_data)):
            print("[DEBUG] 使用缓存的插值网格")
            return self.interpolation_grid
            
        print("[DEBUG] 正在计算新的插值网格...")
        
        # 提取数据
        x, y, z = self.current_data.T
        wafer_radius = self.wafer_size / 2
        
        # 保存副本用于比较变化
        self.cached_data = self.current_data.copy()
        
        # 使用扩展模式创建网格
        scale = wafer_radius * 1.1
        grid_x, grid_y = np.meshgrid(
            np.linspace(-scale, scale, 200),
            np.linspace(-scale, scale, 200)
        )
        
        # 尝试使用RBF插值
        try:
            print("[DEBUG] 尝试使用RBF插值...")
            self.rbf_interpolator = RBFInterpolator(
                np.column_stack([x, y]),
                z,
                kernel='thin_plate_spline',
                neighbors=min(200, len(x)-1)
            )
            grid_z = self.rbf_interpolator(np.column_stack([grid_x.ravel(), grid_y.ravel()]))
            grid_z = grid_z.reshape(grid_x.shape)
            self.last_interpolation_method = "rbf"
            print("[DEBUG] RBF插值成功")
        except Exception as e:
            print(f"[ERROR] RBF插值失败: {e}, 回退到linear")
            self.rbf_interpolator = None
            grid_z = griddata((x, y), z, (grid_x, grid_y), method='linear')
            self.last_interpolation_method = "linear"
        
        # 应用晶圆边界掩码
        distance = np.sqrt(grid_x**2 + grid_y**2)
        grid_z[distance > wafer_radius] = np.nan
        
        # 缓存结果
        self.interpolation_grid = (grid_x, grid_y, grid_z)
        return grid_x, grid_y, grid_z
    


        
    def predict_thickness_at_point(self, x, y):
        """预测指定点的厚度值"""
        if self.rbf_interpolator and self.last_interpolation_method == "rbf":
            try:
                # 使用RBF插值器预测
                return self.rbf_interpolator([[x, y]])[0]
            except Exception as e:
                print(f"[WARN] RBF预测失败: {e}, 回退到griddata")
        
        # 使用缓存的griddata进行插值
        if self.interpolation_grid:
            grid_x, grid_y, grid_z = self.interpolation_grid
            return griddata(
                (grid_x.ravel(), grid_y.ravel()), 
                grid_z.ravel(), 
                (x, y), 
                method='linear'
            )
        
        print("[ERROR] 没有可用的插值器或网格数据")
        return float('nan')
    


    def export_to_new_coords(self):
        """导出数据到新坐标网格 - 优化版"""
        start_time = time.time()
        print(f"[DEBUG] 开始导出到新坐标 @ {time.ctime()}")
        
        if self.current_data is None or len(self.current_data) < 3:
            QMessageBox.warning(self, "数据不足", "需要先加载数据并进行插值")
            print("[ERROR] 导出失败: 当前数据不足")
            return
            
        # 设置网格插值器 - 使用缓存的版本
        try:
            grid_x, grid_y, grid_z = self.setup_grid_interpolator()
            if grid_z is None:
                QMessageBox.warning(self, "内部错误", "无法生成插值网格")
                return
        except Exception as e:
            print(f"[CRITICAL] 设置网格插值器失败: {str(e)}")
            traceback.print_exc()
            QMessageBox.critical(self, "内部错误", f"无法生成插值网格: {str(e)}")
            return
        
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
        x_left = []
        x_right = []
        
        # 向右扩展
        current_x = x_start
        while current_x <= safe_radius:
            x_right.append(current_x)
            current_x += x_step
        
        # 向左扩展
        current_x = x_start - x_step
        while current_x >= -safe_radius:
            x_left.insert(0, current_x)
            current_x -= x_step
        
        x_coords = x_left + x_right
        
        # 生成y坐标序列
        y_lower = []
        y_upper = []
        
        # 向上扩展
        current_y = y_start
        while current_y <= safe_radius:
            y_upper.append(current_y)
            current_y += y_step
        
        # 向下扩展
        current_y = y_start - y_step
        while current_y >= -safe_radius:
            y_lower.insert(0, current_y)
            current_y -= y_step
        
        y_coords = y_lower + y_upper
        
        print(f"[DEBUG] 生成新网格: X点数={len(x_coords)}, Y点数={len(y_coords)}")
        
        # 显示进度对话框
        progress_dialog = QProgressDialog("生成新网格数据...", "取消", 0, len(y_coords), self)
        progress_dialog.setWindowTitle("导出数据")
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
                    distance = (x**2 + y**2)**0.5
                    if distance <= wafer_radius:
                        # 预测厚度
                        thickness = self.predict_thickness_at_point(x, y)
                        
                        # 防止NaN值
                        if not np.isnan(thickness) and abs(thickness) < 1e6:  # 防止溢出
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
        base_name = "_new_Map.csv"
        if self.filename and self.filename != "未加载文件":
            base_name = f"{os.path.splitext(self.filename)[0]}_new_Map.csv"
        
        save_path = save_file_dialog(
            "保存新坐标数据",
            default_path=base_name,
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
                                f"已成功导出数据至 {os.path.basename(save_path)}\n"
                                f"生成数据点: {valid_points} 个")
        except Exception as e:
            print(f"[ERROR] 保存文件失败: {str(e)}")
            QMessageBox.critical(self, "保存失败", f"无法保存文件: {str(e)}")

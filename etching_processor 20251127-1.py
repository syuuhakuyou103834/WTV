import numpy as np
import pandas as pd
import scipy.interpolate
from scipy.fft import fft2, ifft2, fftshift, ifftshift
from scipy.ndimage import gaussian_filter, convolve as ndi_convolve
import logging
import csv
import os
import time
from scipy.interpolate import RBFInterpolator, griddata
from core.convolution_engine import ConvolutionEngine  # 导入卷积引擎

class IonBeamProcessor:
    def __init__(self, grid_size=170.0, resolution=1.0, wafer_diameter=150.0, extend_edge=True, transition_width=50.0):
        """
        初始化离子束刻蚀处理器 - 修复网格坐标问题

        关键修改:
        - 修正 n_pixels 计算方式 (point_count = (grid_size/resolution) + 1)
        - 确保网格点数量正确，步长严格等于分辨率
        - 添加可配置的过渡区宽度参数
        """
        self.grid_size = grid_size
        self.resolution = resolution
        self.wafer_diameter = wafer_diameter
        self.transition_width = transition_width  # 可配置的过渡区宽度
        
        # === 关键修复: 正确计算网格点数量 ===
        # 点数 = (网格尺寸/分辨率) + 1
        # 例如: grid_size=200, resolution=1.0 → 201点
        point_count = int(grid_size / resolution) + 1
        self.n_pixels = point_count
        
        # 创建固定步长的网格坐标
        # 从 -grid_size/2 到 +grid_size/2 (含端点)
        self.grid_points = np.linspace(-grid_size/2, grid_size/2, point_count)
        self.X, self.Y = np.meshgrid(self.grid_points, self.grid_points)

        # 添加卷积引擎
        self.conv_engine = ConvolutionEngine()
        
        self.log(f"初始完成: {self.n_pixels}x{self.n_pixels} 网格, 分辨率 {resolution} mm/pixel")
        self.log(f"X坐标范围: {np.min(self.X):.1f} 到 {np.max(self.X):.1f} mm")
        self.log(f"坐标步长: {self.grid_points[1] - self.grid_points[0]:.4f} mm (应等于分辨率)")
        
        # 创建晶圆掩模
        self.wafer_radius = wafer_diameter / 2
        self.wafer_mask = self.create_wafer_mask(extend=False)
        
        # 创建径向距离图 (用于平滑外推)
        self.r_distance = np.sqrt(self.X**2 + self.Y**2)
        
        # 设置最小/最大速度限制
        self.min_speed = 0.01  # mm/s
        self.max_speed = 500.0  # mm/s
        self.base_etch_rate = 1.0  # nm/s (将被归一化)

        # 添加扩展边界参数
        self.extend_edge = extend_edge
        
        # 添加新的属性
        self.target_thickness = 1800.0  # 默认目标膜厚
        self.initial_thickness_stats = {}  # 初始膜厚统计信息
        self.etching_depth_map = None  # 刻蚀深度分布

        self.simulated_etch_depth = None  # 卷积验算得到的刻蚀深度
        self.validated_thickness_map = None  # 验算后的膜厚
    
    def log(self, message):
        """简单的日志记录函数"""
        print(f"[{time.strftime('%H:%M:%S')}] {message}")
        
    def create_wafer_mask(self, extend=False):
        """创建晶圆区域的掩模
        extend: 是否将掩模略微扩展到晶圆边界之外
        """
        r = np.sqrt(self.X**2 + self.Y**2)
        if extend:
            # 将掩模略微扩展到晶圆外部1像素边界
            mask = r <= (self.wafer_radius + self.resolution)
        else:
            mask = r <= self.wafer_radius
        return mask
    
    def calculate_thickness_stats(self, thickness_map):
        """计算膜厚统计特征"""
        if thickness_map is None:
            return {
                'min': 0,
                'max': 0,
                'mean': 0,
                'range': 0,
                'uniformity': 0
            }

        # 使用晶圆掩模获取晶圆内部的数据
        wafer_data = thickness_map[self.wafer_mask]
        
        # 计算基本统计信息
        min_val = np.min(wafer_data)
        max_val = np.max(wafer_data)
        mean_val = np.mean(wafer_data)
        
        # 计算膜厚均一性: U% = 100 * Range / (2 * average)
        range_val = max_val - min_val
        uniformity = 100.0 * range_val / (2 * mean_val) if mean_val != 0 else 0
        
        return {
            'min': min_val,
            'max': max_val,
            'mean': mean_val,
            'range': range_val,
            'uniformity': uniformity
        }

    def calculate_etch_amount_stats(self):
        """计算刻蚀量统计特征（初始膜厚 - 刻蚀后膜厚）"""
        if not hasattr(self, 'initial_thickness_map') or not hasattr(self, 'get_validated_thickness_map'):
            return None

        # 获取刻蚀后膜厚
        result_thickness_map = self.get_validated_thickness_map()
        if result_thickness_map is None:
            return None

        # 计算刻蚀量 = 初始膜厚 - 刻蚀后膜厚
        etch_amount_map = self.initial_thickness_map - result_thickness_map

        # 使用晶圆掩模获取晶圆内部的数据
        wafer_etch_data = etch_amount_map[self.wafer_mask]

        # 计算基本统计信息
        min_val = np.min(wafer_etch_data)
        max_val = np.max(wafer_etch_data)
        mean_val = np.mean(wafer_etch_data)

        # 计算刻蚀量均一性: U% = 100 * Range / (2 * average)
        range_val = max_val - min_val
        uniformity = 100.0 * range_val / (2 * mean_val) if mean_val != 0 else 0 if mean_val > 0 else 0

        return {
            'min': min_val,
            'max': max_val,
            'mean': mean_val,
            'range': range_val,
            'uniformity': uniformity
        }

    def load_etching_data(self, file_path):
        """
        加载刻蚀量数据并进行先进的外推插值
        
        参数:
        file_path: 刻蚀量数据文件路径
        
        返回:
        160x160网格上的刻蚀量分布
        """
        self.log(f"加载刻蚀数据: {file_path}")
        df = pd.read_csv(file_path)
        
        # 智能检测厚度列名(关键修复)
        thickness_col = None
        if 'Thickness(nm)' in df.columns:
            thickness_col = 'Thickness(nm)'
        elif 'Thickness' in df.columns:
            thickness_col = 'Thickness'
        elif 'thickness' in df.columns:
            thickness_col = 'thickness'
        elif 'value' in df.columns:
            thickness_col = 'THKs'
        
        if not thickness_col:
            # 尝试寻找第一个数值列
            for col in df.columns:
                try:
                    # 检查列是否包含数值类型数据
                    if pd.api.types.is_numeric_dtype(df[col]) or all(isinstance(x, (int, float)) for x in df[col].head(3)):
                        thickness_col = col
                        self.log(f"自动选择列 '{col}' 作为厚度数据")
                        break
                except Exception:
                    continue
                    
        if not thickness_col:
            # 如果仍有问题，使用最后一个列作为厚度数据(常见模式)
            if len(df.columns) >= 3:
                thickness_col = df.columns[2]
                self.log(f"警告：使用第3列作为厚度数据: {thickness_col}")
        
        if not thickness_col:
            raise ValueError("无法识别厚度数据列名，请确保CSV文件包含有效的厚度数据列")
        
        # 智能检测X,Y列名
        x_col = None
        y_col = None
        for col in df.columns:
            col_lower = col.lower()
            if col_lower == 'x' and x_col is None:
                x_col = col
            elif col_lower == 'y' and y_col is None:
                y_col = col

        # 如果没找到小写的，尝试大写
        if x_col is None and 'X' in df.columns:
            x_col = 'X'
        if y_col is None and 'Y' in df.columns:
            y_col = 'Y'

        if not x_col or not y_col:
            raise ValueError(f"无法识别X,Y列名. 找到的列: {list(df.columns)}")

        x = df[x_col].values
        y = df[y_col].values
        thickness = df[thickness_col].values
        
        # 关键修复: 根据新的网格点数量创建插值网格
        grid_size = self.grid_size
        wafer_radius = self.wafer_radius
        point_count = self.n_pixels  # 使用新的点数量
        
        # 计算网格尺寸（确保覆盖整个晶圆区域）
        x_min = -grid_size / 2
        x_max = grid_size / 2
        y_min = -grid_size / 2
        y_max = grid_size / 2
        
        # 创建覆盖整个网格的坐标
        grid_x, grid_y = np.meshgrid(
            np.linspace(x_min, x_max, point_count),
            np.linspace(y_min, y_max, point_count)
        )
        
        # === 使用与single_wafer_ui一致的插值方法 ===
        # 选择插值方法
        if self.extend_edge:
            # 扩展模式优先使用RBF插值
            try:
                # 使用薄板样条径向基函数插值
                rbf = RBFInterpolator(
                    np.column_stack([x, y]),
                    thickness,
                    kernel='thin_plate_spline',
                    neighbors=min(200, len(x)-1)
                )
                grid_points = np.column_stack([grid_x.ravel(), grid_y.ravel()])
                thickness_grid = rbf(grid_points).reshape(grid_x.shape)
            except Exception as e:
                self.log(f"RBF插值失败: {str(e)}, 回退到线性插值")
                thickness_grid = griddata(
                    (x, y), thickness, 
                    (grid_x, grid_y), 
                    method='linear',
                    fill_value=thickness.min()
                )
        else:
            # 非扩展模式使用多层尝试的网格插值
            for method in ['cubic', 'linear', 'nearest']:
                try:
                    thickness_grid = griddata(
                        (x, y), thickness, 
                        (grid_x, grid_y), 
                        method=method,
                        fill_value=thickness.min()
                    )
                    self.log(f"使用 {method} 插值成功")
                    break
                except Exception as e:
                    self.log(f"{method}插值失败: {str(e)}")
                    continue
            else:
                raise RuntimeError("所有插值方法均失败")
        
        # 确保最小值不为零（避免后续计算问题）
        min_value = np.max([thickness_grid.min(), 0.01])
        thickness_grid[thickness_grid < min_value] = min_value
        
        # 存储数据网格
        self.X = grid_x
        self.Y = grid_y
        
        # 计算径向距离和晶圆掩膜
        self.r_distance = np.sqrt(grid_x**2 + grid_y**2)
        wafer_mask = self.r_distance <= wafer_radius
        self.wafer_mask = wafer_mask
        
        self.log(f"刻蚀数据插值完成，网格尺寸: {grid_x.shape}")
        self.log(f"坐标步长验证: X方向 = {self.X[0,1] - self.X[0,0]:.4f} mm, Y方向 = {self.Y[1,0] - self.Y[0,0]:.4f} mm")
        
        # 存储初始膜厚和计算统计信息
        self.initial_thickness_map = thickness_grid
        self.initial_thickness_stats = self.calculate_thickness_stats(thickness_grid)
        
        # 计算刻蚀深度分布
        self.calculate_etching_depth()
        
        return thickness_grid
    
    def set_target_thickness(self, target):
        """设置目标膜厚并计算刻蚀深度"""
        self.target_thickness = target
        self.calculate_etching_depth()
        return True
    
    def calculate_etching_depth(self):
        """
        根据目标膜厚计算刻蚀深度
        
        原理:
        - 如果目标膜厚 < 初始膜厚最小值: 刻蚀深度 = 初始膜厚 - 目标膜厚
        - 如果目标膜厚 > 初始膜厚最小值: 
            正刻蚀深度区域: 初始膜厚 > 目标膜厚
            负刻蚀深度区域: 初始膜厚 < 目标膜厚 -> 不需要刻蚀 (设为0)
        """
        if not hasattr(self, 'initial_thickness_map'):
            return False
            
        # 计算基本刻蚀深度
        etching_depth = np.zeros_like(self.initial_thickness_map)
        initial_min = self.initial_thickness_stats['min']
        
        # 情况1: 目标膜厚小于初始最小值
        if self.target_thickness < initial_min:
            etching_depth = self.initial_thickness_map - self.target_thickness
        # 情况2: 目标膜厚大于初始最小值
        else:
            # 创建掩模: 仅刻蚀初始膜厚大于目标的区域
            mask = self.initial_thickness_map > self.target_thickness
            # 设置正刻蚀深度
            etching_depth[mask] = self.initial_thickness_map[mask] - self.target_thickness
        
        self.etching_depth_map = etching_depth
        return etching_depth
    
    def get_results_thickness_map(self):
        """获取刻蚀后膜厚结果图"""
        if not hasattr(self, 'initial_thickness_map') or self.etching_depth_map is None:
            return None
            
        # 计算刻蚀后膜厚 = 初始膜厚 - 刻蚀深度
        result_map = self.initial_thickness_map.copy()
        wafer_mask = self.r_distance <= self.wafer_radius
        
        # 仅在晶圆区域内减去刻蚀深度 (外部保留初始值)
        result_map[wafer_mask] -= self.etching_depth_map[wafer_mask]
        
        return result_map
    
    def load_beam_profile(self, file_path):
        """
        加载离子束强度分布（修正版本）
        用户提供的离子束单位是nm/s（每秒刻蚀厚度），不应进行归一化处理
        """
        self.log(f"加载离子束数据: {file_path}")
        
        # 读取原始离子束数据
        data = []
        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if row:  # 跳过空行
                    # 将空字符串转换为0
                    processed_row = []
                    for val in row:
                        if val.strip() == '':
                            processed_row.append(0.0)
                        else:
                            try:
                                # 保留原始值（单位：nm/s）
                                processed_row.append(float(val.strip()))
                            except ValueError:
                                processed_row.append(0.0)
                    data.append(processed_row)
        
        # 转换为NumPy数组
        max_width = max(len(row) for row in data) if data else 0
        padded_data = []
        for row in data:
            if len(row) < max_width:
                row += [0.0] * (max_width - len(row))
            padded_data.append(row)
        
        beam_original = np.array(padded_data)
        self.log(f"原始离子束尺寸: {beam_original.shape}")
        self.log(f"离子束最大刻蚀率: {beam_original.max():.4f} nm/s, 最小值: {beam_original.min():.4f} nm/s")
        
        ######################################################
        # 关键修改：不再进行归一化处理，保留原始离子束值 (nm/s)
        ######################################################
        
        # 将小尺寸的离子束投影到大网格上
        beam_grid = np.zeros_like(self.X)
        
        # 计算位置偏移
        beam_h, beam_w = beam_original.shape
        start_x = (self.n_pixels - beam_w) // 2
        start_y = (self.n_pixels - beam_h) // 2
        end_x = start_x + beam_w
        end_y = start_y + beam_h
        
        # 放置离子束（使用原始nm/s值）
        beam_grid[start_y:end_y, start_x:end_x] = beam_original
        
        # 应用轻微高斯模糊以减少FFT振铃效应
        beam_grid = gaussian_filter(beam_grid, sigma=0.5)
        
        # 直接使用原始值（单位：nm/s）
        self.beam_profile = beam_grid
        
        # 用于卷积验算的离子束同样保留原始值
        self.raw_ion_beam = beam_original.copy()
        
        self.log(f"离子束处理完成：最大刻蚀率={beam_grid.max():.4f} nm/s")
        
        return self.beam_profile
    
    def calculate_dwell_time(self, regularization=1e-3):
        """
        修复象限颠倒问题的停留时间计算
        
        注意: 现在使用蚀刻深度图(self.etching_depth_map)计算停留时间
        """
        # 验证蚀刻深度图
        if self.etching_depth_map is None:
            self.log("错误: 未计算刻蚀深度图")
            return None
            
        self.log("开始反卷积计算停留时间(修复象限)...")
        
        # 1. 获取蚀刻深度和光束分布
        E = self.etching_depth_map
        I = self.beam_profile
        
        # 2. 添加零填充减少边界效应
        pad_size = self.n_pixels // 2
        E_padded = np.pad(E, pad_size, mode='constant', constant_values=0)
        I_padded = np.pad(I, pad_size, mode='constant', constant_values=0)
        
        # 3. 正确的相位处理(关键修复)
        # 将零点移到频谱中心
        E_shifted = ifftshift(E_padded)
        I_shifted = ifftshift(I_padded)
        
        # 4. FFT计算
        F_E = fft2(E_shifted)
        F_I = fft2(I_shifted)
        
        # 5. 计算功率谱
        I_power = np.abs(F_I)**2
        
        # 6. 维纳滤波器
        epsilon = 1.0 / regularization
        wiener_filter = np.conjugate(F_I) / (I_power + epsilon)
        
        # 7. 反卷积
        F_D = F_E * wiener_filter
        
        # 8. 逆傅里叶变换
        D_shifted = ifft2(F_D)
        
        # 9. 移回空间坐标(关键修复)
        dwell_padded = fftshift(D_shifted)
        
        # 10. 移除填充
        dwell_time = np.real(dwell_padded[pad_size:-pad_size, pad_size:-pad_size])
        
        # 11. 设置最小值保证物理合理性
        dwell_min = 0.1 / self.max_speed
        dwell_time = np.maximum(dwell_time, dwell_min)
        
        self.dwell_time = dwell_time
        self.log(f"停留时间计算完成，范围: {dwell_time.min():.4f}-{dwell_time.max():.4f} 秒")
        self.dwell_time_map = dwell_time  # 存储停留时间地图
        return dwell_time
    
    def calculate_velocity_map(self):
        """根据停留时间计算速度分布（改进版）"""
        if self.dwell_time is None:
            self.log("错误: 未计算停留时间")
            return None
            
        self.log("计算速度分布（优化过渡区）...")
        
        # 基本速度计算
        with np.errstate(divide='ignore'):
            velocity = np.divide(1.0, self.dwell_time, 
                                out=np.full_like(self.dwell_time, self.max_speed),
                                where=self.dwell_time > 1e-6)
        
        # 物理限制
        velocity = np.clip(velocity, self.min_speed, self.max_speed)
        
        # 1. 晶圆内部保持原始计算速度
        inner_mask = self.r_distance <= self.wafer_radius
        
        # 2. 使用可配置的过渡区宽度
        transition_width = self.transition_width  # 使用用户配置的过渡区宽度

        # 3. 晶圆外部（不包括过渡区）设为最大速度
        outer_mask = self.r_distance > self.wafer_radius + transition_width
        velocity[outer_mask] = self.max_speed
        
        # 4. 晶圆外部过渡区（使用用户配置的宽度）
        transition_mask = np.logical_and(
            self.r_distance > self.wafer_radius,
            self.r_distance <= self.wafer_radius + transition_width
        )
        
        # 5. 从晶圆边缘处的速度平滑过渡到最大速度
        weight = (self.r_distance[transition_mask] - self.wafer_radius) / transition_width
        velocity[transition_mask] = (
            (1 - weight) * velocity[transition_mask] + 
            weight * self.max_speed
        )
        
        self.velocity_map = velocity
        self.log(f"速度计算完成（过渡区宽度: {self.transition_width}mm），范围: {velocity.min():.4f}-{velocity.max():.4f} mm/s")
        return velocity
    
    def generate_trajectory_recipe(self, filename="stage_recipe.csv"):
        """
        生成载台运动轨迹Recipe
        
        参数:
        filename: 输出文件名
        """
        self.log(f"生成载台轨迹: {filename}")
        
        # 提取有效点 (整个160x160网格)
        points = []
        for i in range(self.n_pixels):
            for j in range(self.n_pixels):
                x = self.X[i, j]
                y = self.Y[i, j]
                speed = self.velocity_map[i, j]
                
                # 应用速度限制
                speed = max(self.min_speed, min(self.max_speed, speed))
                points.append((x, y, speed))
        
        # 按Y（主）、X（副）排序 - 典型光栅扫描顺序
        points.sort(key=lambda p: (-p[1], p[0]))
        
        # 保存到CSV
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["X(mm)", "Y(mm)", "Velocity(mm/s)"])
                for (x, y, speed) in points:
                    writer.writerow([f"{x:.3f}", f"{y:.3f}", f"{speed:.6f}"])
            self.log(f"轨迹文件保存成功，共 {len(points)} 个点")
        except Exception as e:
            self.log(f"保存轨迹失败: {str(e)}")
            
    def save_dwell_time_map(self, filename="dwell_time_map.csv"):
        """
        保存停留时间地图为矩阵格式的CSV文件，格式要求：
        第一行: Y\\X, x1, x2, ..., xn
        第一列: y1, time, ...
                y2, time, ...
        """
        if not hasattr(self, 'dwell_time'):
            self.log("错误: 未计算停留时间地图")
            return False
            
        try:
            # 获取完整的网格坐标（不要跳过任何点）
            x_coords = self.grid_points
            y_coords = self.grid_points
            
            # 创建DataFrame，行索引为Y坐标，列名为X坐标
            df = pd.DataFrame(
                self.dwell_time,
                index=y_coords,
                columns=x_coords
            )
            
            # 重置索引并将Y坐标列命名为"Y\\X"
            df = df.reset_index()
            df.rename(columns={'index': 'Y\\X'}, inplace=True)
            
            # 保存到CSV，格式化为5位小数
            df.to_csv(filename, index=False, float_format='%.5f')
            
            self.log(f"停留时间地图已保存为: {filename}")
            return True
        except Exception as e:
            self.log(f"保存停留时间地图失败: {str(e)}")
            return False
        
    def save_velocity_map(self, filename="velocity_map.csv"):
        """
        保存速度分布地图 - 修复坐标步长问题
        关键修改: 确保使用正确的网格点坐标
        """
        if not hasattr(self, 'velocity_map'):
            self.log("错误: 未计算速度地图")
            return False
            
        try:
            # 获取完整的网格坐标 (已经修正)
            x_coords = self.grid_points  # [-100, -99, ..., 99, 100] (步长1mm)
            y_coords = self.grid_points  # [-100, -99, ..., 99, 100] (步长1mm)
            
            # 确保速度矩阵尺寸与坐标数量匹配
            if (len(y_coords), len(x_coords)) != self.velocity_map.shape:
                self.log(f"警告: 速度矩阵尺寸不匹配 ({self.velocity_map.shape} vs {(len(y_coords), len(x_coords))})")
                
                # 裁剪或填充以匹配指定的网格尺寸
                target_shape = (len(y_coords), len(x_coords))
                padded_velocity = np.full(target_shape, self.max_speed)
                
                # 将现有数据复制到新矩阵中
                rows = min(target_shape[0], self.velocity_map.shape[0])
                cols = min(target_shape[1], self.velocity_map.shape[1])
                padded_velocity[:rows, :cols] = self.velocity_map[:rows, :cols]
                cropped_velocity = padded_velocity
                self.log(f"已将速度矩阵调整为指定网格尺寸 {target_shape}")
            else:
                cropped_velocity = self.velocity_map
            
            # 创建DataFrame，行索引为Y坐标，列名为X坐标
            df = pd.DataFrame(
                cropped_velocity,
                index=y_coords,
                columns=x_coords
            )
            
            # 重置索引并将Y坐标列命名为"Y\\X"
            df = df.reset_index()
            df.rename(columns={'index': 'Y\\X'}, inplace=True)
            
            # 保存到CSV
            df.to_csv(filename, index=False, float_format='%.10f')
            
            self.log(f"速度分布地图已保存为: {filename}")
            self.log(f"网格尺寸: {len(y_coords)}x{len(x_coords)}")
            self.log(f"坐标范围: X({x_coords[0]:.1f} to {x_coords[-1]:.1f}), Y({y_coords[0]:.1f} to {y_coords[-1]:.1f})")
            self.log(f"坐标步长: ΔX = {x_coords[1]-x_coords[0]:.6f} mm, ΔY = {y_coords[1]-y_coords[0]:.6f} mm")
            
            return True
        except Exception as e:
            self.log(f"保存速度分布地图失败: {str(e)}")
            return False
    
    def save_thickness_map(self, filename="thickness_map.csv", map_type="initial"):
        """
        保存膜厚分布图
        
        参数:
        map_type: "initial" - 初始膜厚
                  "result" - 刻蚀后膜厚
                  "etching_depth" - 刻蚀深度
        """
        if map_type == "initial":
            data = self.initial_thickness_map
            title = "初始膜厚"
        elif map_type == "result":
            data = self.get_results_thickness_map()
            if data is None:
                self.log("错误: 未计算刻蚀后膜厚")
                return False
            title = "刻蚀后膜厚"
        elif map_type == "etching_depth":
            if self.etching_depth_map is None:
                self.log("错误: 未计算刻蚀深度")
                return False
            data = self.etching_depth_map
            title = "刻蚀深度"
        else:
            self.log("错误: 不支持的地图类型")
            return False
            
        try:
            # 获取完整的网格坐标
            x_coords = self.grid_points
            y_coords = self.grid_points
            
            # 创建DataFrame
            df = pd.DataFrame(
                data,
                index=y_coords,
                columns=x_coords
            )
            
            # 重置索引并将Y坐标列命名为"Y\\X"
            df = df.reset_index()
            df.rename(columns={'index': 'Y\\X'}, inplace=True)
            
            # 保存到CSV
            df.to_csv(filename, index=False, float_format='%.2f')
            self.log(f"{title}地图已保存为: {filename}")
            return True
        except Exception as e:
            self.log(f"保存{title}地图失败: {str(e)}")
            return False
    
    def convolve_dwell_time(self):
        """
        使用卷积引擎计算模拟刻蚀深度
        直接调用外部卷积引擎确保一致性
        """
        self.log("开始卷积验算: 停留时间 × 离子束轮廓 → 模拟刻蚀深度")
        
        # 确保有停留时间和离子束数据
        if self.dwell_time is None or self.raw_ion_beam is None:
            self.log("错误: 停留时间或原始离子束未加载")
            return np.zeros_like(self.X) if hasattr(self, 'X') else np.zeros((170, 170))
        
        try:
            # 设置卷积参数
            self.conv_engine.circle_diameter = self.wafer_diameter
            self.conv_engine.center_x = 0
            self.conv_engine.center_y = 0
            
            # 临时保存停留时间数据
            dwell_path = "temp_dwell_time.csv"
            self.save_dwell_time_map(dwell_path)
            
            # 临时保存离子束数据
            beam_path = "temp_ion_beam.csv"
            np.savetxt(beam_path, self.raw_ion_beam, delimiter=",")
            
            # 使用卷积引擎计算
            heatmap_path, csv_path = self.conv_engine.process_etch_depth(dwell_path, beam_path)
            
            # 加载计算结果
            df = pd.read_csv(csv_path, index_col=0)
            simulated_etch_depth = df.values
            self.log(f"从卷积引擎加载验算刻蚀深度: {simulated_etch_depth.shape}")
            
            # 删除临时文件
            os.remove(dwell_path)
            os.remove(beam_path)
            
            self.simulated_etch_depth = simulated_etch_depth
            
            # 结果统计 - 关键修改: 仅计算晶圆内部区域
            # 验算刻蚀深度统计
            sim_stats = self.calculate_thickness_stats(simulated_etch_depth)
            self.log(f"验算刻蚀深度统计(晶圆内部): 最小值={sim_stats['min']:.2f}nm, 最大值={sim_stats['max']:.2f}nm, 平均值={sim_stats['mean']:.2f}nm")
            
            # 目标刻蚀深度统计 - 仅使用晶圆内部区域
            target_etch_stats = self.calculate_thickness_stats(self.etching_depth_map)
            self.log(f"目标刻蚀深度(晶圆内部): 最小值={target_etch_stats['min']:.2f}nm, 最大值={target_etch_stats['max']:.2f}nm, 平均值={target_etch_stats['mean']:.2f}nm")
            
            # 计算均方误差 - 仅针对晶圆内部区域
            wafer_mask = self.wafer_mask
            mse = np.mean((simulated_etch_depth[wafer_mask] - self.etching_depth_map[wafer_mask]) ** 2)
            self.log(f"验算与目标刻蚀深度的均方误差(MSE)(晶圆内部): {mse:.4f}")
            
            return simulated_etch_depth
        except Exception as e:
            self.log(f"卷积验算错误: {str(e)}")
            return np.zeros_like(self.X) if hasattr(self, 'X') else np.zeros((170, 170))
    
    def get_validated_thickness_map(self):
        """获取验算后膜厚: 初始膜厚 - 卷积得到的模拟刻蚀深度"""
        if self.initial_thickness_map is None or self.simulated_etch_depth is None:
            return None
            
        # 计算验算后膜厚 = 初始膜厚 - 模拟刻蚀深度
        result_map = self.initial_thickness_map.copy()
        wafer_mask = self.r_distance <= self.wafer_radius
        
        # 仅在晶圆区域内减去模拟刻蚀深度
        result_map[wafer_mask] -= self.simulated_etch_depth[wafer_mask]
        
        return result_map

    def process_etching_simulation(self, etching_file, beam_file, output_dir):
        """
        完整的刻蚀模拟流程
        返回结果文件路径字典
        """
        results = {}
        try:
            # 处理数据
            self.load_etching_data(etching_file)
            self.load_beam_profile(beam_file)
            
            # 保存初始膜厚数据
            thickness_file = os.path.join(output_dir, "initial_thickness_map.csv")
            self.save_thickness_map(thickness_file, "initial")
            results['initial_thickness_map'] = thickness_file
            
            # 保存目标刻蚀深度数据
            etching_depth_file = os.path.join(output_dir, "etching_depth_map.csv")
            self.save_thickness_map(etching_depth_file, "etching_depth")
            results['etching_depth_map'] = etching_depth_file
            
            # 计算停留时间和速度
            self.calculate_dwell_time()
            self.calculate_velocity_map()

             # 新增：保存停留时间地图前记录统计
            dwell_total = np.sum(self.dwell_time)
            self.log(f"停留时间总和: {dwell_total:.2f} 秒")
            
            # 卷积验算停留时间准确性
            self.convolve_dwell_time()

            # 新增：保存模拟刻蚀深度（用于调试）
            simulated_etch_file = os.path.join(output_dir, "simulated_etch_depth.csv")
            self.save_thickness_map(simulated_etch_file, "simulated_etch")
            results['simulated_etch_depth'] = simulated_etch_file
            
            # 保存验算后膜厚数据
            validated_thickness_file = os.path.join(output_dir, "validated_thickness_map.csv")
            self.save_thickness_map(validated_thickness_file, "validated")
            results['validated_thickness_map'] = validated_thickness_file
            
            # 保存停留时间地图
            dwell_time_file = os.path.join(output_dir, "dwell_time_map.csv")
            self.save_dwell_time_map(dwell_time_file)
            results['dwell_time_map'] = dwell_time_file

            # 保存速度分布地图
            velocity_map_file = os.path.join(output_dir, "velocity_map.csv")
            self.save_velocity_map(velocity_map_file)
            results['velocity_map'] = velocity_map_file
            
            # 生成轨迹文件
            recipe_file = os.path.join(output_dir, "stage_recipe.csv")
            self.generate_trajectory_recipe(recipe_file)
            results['stage_recipe'] = recipe_file
            
            # 返回统计信息
            try:
                # 验算后膜厚的统计信息
                validated_map = self.get_validated_thickness_map()
                validated_stats = self.calculate_thickness_stats(validated_map) if validated_map is not None else {
                    'min': 0, 'max': 0, 'mean': 0, 'range': 0, 'uniformity': 0
                }
                
                results['initial_thickness_stats'] = self.initial_thickness_stats
                results['target_thickness'] = self.target_thickness
                results['validated_thickness_stats'] = validated_stats
                results['output_dir'] = output_dir
            except Exception as e:
                self.log(f"统计数据无法生成: {str(e)}")
            
            return results
            
        except Exception as e:
            self.log(f"刻蚀模拟失败: {str(e)}")
            # 返回空结果字典而不是None
            return {
                'initial_thickness_map': '',
                'etching_depth_map': '',
                'simulated_etch_depth': '',
                'validated_thickness_map': '',
                'dwell_time_map': '',
                'velocity_map': '',
                'stage_recipe': '',
                'initial_thickness_stats': {},
                'target_thickness': 0,
                'validated_thickness_stats': {},
                'error': str(e)
            }
    
    def save_thickness_map(self, filename="thickness_map.csv", map_type="initial"):
        """
        保存膜厚分布图
        
        参数:
        map_type: "initial" - 初始膜厚
                  "etching_depth" - 刻蚀深度
                  "validated" - 验算后膜厚
        """
        if map_type == "initial":
            data = self.initial_thickness_map
            title = "初始膜厚"
        elif map_type == "validated":
            if not hasattr(self, 'validated_thickness_map') or self.validated_thickness_map is None:
                # 动态计算验算膜厚
                self.validated_thickness_map = self.get_validated_thickness_map()
                if self.validated_thickness_map is None:
                    self.log("错误: 未计算验算膜厚")
                    return False
            data = self.validated_thickness_map
            title = "验算膜厚"
        elif map_type == "etching_depth":
            if self.etching_depth_map is None:
                self.log("错误: 未计算刻蚀深度")
                return False
            data = self.etching_depth_map
            title = "刻蚀深度"
        elif map_type == "simulated_etch":  # 新增用于调试
            if self.simulated_etch_depth is None:
                self.log("错误: 未计算模拟刻蚀深度")
                return False
            data = self.simulated_etch_depth
            title = "模拟刻蚀深度"
        else:
            self.log("错误: 不支持的地图类型")
            return False
            
        try:
            # 获取完整的网格坐标
            x_coords = self.grid_points
            y_coords = self.grid_points
            
            # 创建DataFrame
            df = pd.DataFrame(
                data,
                index=y_coords,
                columns=x_coords
            )
            
            # 重置索引并将Y坐标列命名为"Y\\X"
            df = df.reset_index()
            df.rename(columns={'index': 'Y\\X'}, inplace=True)
            
            # 保存到CSV
            df.to_csv(filename, index=False, float_format='%.5f')
            self.log(f"{title}地图已保存为: {filename}")
            return True
        except Exception as e:
            self.log(f"保存{title}地图失败: {str(e)}")
            return False

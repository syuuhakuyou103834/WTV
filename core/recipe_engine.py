import numpy as np
import matplotlib.pyplot as plt
import csv
import os
from scipy.interpolate import interp1d

class RecipeEngine:
    def __init__(self):
        # 初始化引擎变量
        self.speed_matrix = None
        self.dwell_matrix = None
        self.x_coords = None
        self.y_coords = None
        self.y_coords_1mm = None
        self.x_grid = None  # 均匀网格X坐标
        self.y_grid = None  # 均匀网格Y坐标
        self.speed_heatmap_path = None
        self.dwell_heatmap_path = None
        
        # 圆形区域参数
        self.circle_mode = False
        self.circle_style = "jet"
        self.circle_diameter = 0
        self.center_x = 0
        self.center_y = 0
        
        # 镜像参数
        self.mirror_y = False  # 新增镜像标志
    
    def set_circle_params(self, diameter, center_x, center_y):
        """设置圆形区域参数"""
        self.circle_diameter = diameter
        self.center_x = center_x
        self.center_y = center_y
    
    def create_circle_mask(self, X, Y, center_x, center_y, diameter):
        """创建圆形遮罩"""
        # 计算半径
        radius = diameter / 2.0
        
        # 计算每个点到圆心的距离
        distance = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
        
        # 创建遮罩（距离 <= 半径的点为True）
        mask = distance <= radius
        
        return mask
    
    def apply_circle_mask(self, matrix, x_coords, y_coords):
        """应用圆形遮罩到矩阵"""
        # 创建网格坐标
        X, Y = np.meshgrid(x_coords, y_coords)
        
        # 创建圆形遮罩
        mask = self.create_circle_mask(X, Y, self.center_x, self.center_y, self.circle_diameter)
        
        # 复制矩阵，将遮罩外部设为NaN
        masked_matrix = matrix.copy()
        masked_matrix[~mask] = np.nan
        
        return masked_matrix
    
    def fill_matrix(self, matrix):
        """填充矩阵中的空缺值（NaN）使用周围相邻值平均值"""
        def get_neighbors(i, j):
            """获取有效的相邻值"""
            neighbors = []
            # 上方邻居 (i-1, j)
            if i-1 >= 0 and not np.isnan(matrix[i-1,j]):
                neighbors.append(matrix[i-1,j])
            # 下方邻居 (i+1, j)
            if i+1 < matrix.shape[0] and not np.isnan(matrix[i+1,j]):
                neighbors.append(matrix[i+1,j])
            # 左方邻居 (i, j-1)
            if j-1 >= 0 and not np.isnan(matrix[i,j-1]):
                neighbors.append(matrix[i,j-1])
            # 右方邻居 (i, j+1)
            if j+1 < matrix.shape[1] and not np.isnan(matrix[i,j+1]):
                neighbors.append(matrix[i,j+1])
            return neighbors
        
        # 复制矩阵以免修改原数据
        filled_matrix = matrix.copy()
        rows, cols = filled_matrix.shape
        
        # 检查每个单元格是否需要填充
        for i in range(rows):
            for j in range(cols):
                if np.isnan(filled_matrix[i,j]):
                    neighbors = get_neighbors(i, j)
                    if neighbors:
                        filled_matrix[i, j] = np.mean(neighbors)
        return filled_matrix
    
    def process_recipe(self, file_path):
        """主处理函数，读取并处理Recipe文件"""
        # 确保输出目录存在
        output_dir = os.path.abspath("Data/recipe_analysis/")
        os.makedirs(output_dir, exist_ok=True)
        
        # 读取数据
        points_data = []
        x_set = set()
        y_set = set()
        header_found = False
        
        with open(file_path, 'r') as f:
            reader = csv.reader(f, skipinitialspace=True)
            
            # 表头检测
            for row in reader:
                if not row:
                    continue
                    
                if len(row) >= 5:
                    header_candidates = [col.strip().lower() for col in row[:5]]
                    required_headers = {"point", "x-position", "x-speed", "y-position", "y-speed"}
                    
                    if required_headers.issubset(set(header_candidates)):
                        header_found = True
                        break
            
            if not header_found:
                print("错误：未找到有效表头")
                return None, None, None, None
            
            # 数据处理
            for row in reader:
                if not row:
                    continue
                    
                # 检查结束行 (放在数据提取之前)
                if len(row) >= 5:
                    try:
                        # 精确匹配结束行 (0,0,0,0,0)
                        if all(abs(float(val)) < 1e-10 for val in row[:5]):
                            break
                    except:
                        pass
                
                # 数据提取 (所有单位都是mm)
                try:
                    point = int(row[0])
                    x_pos = float(row[1])  # 单位为mm
                    y_pos = float(row[3])  # 单位为mm
                    y_speed = float(row[4])  # 单位为mm/s
                    
                    # 添加坐标验证和零速度检查
                    if abs(x_pos) < 1e-10 or abs(y_pos) < 1e-10 or abs(y_speed) < 1e-10:
                        continue
                        
                    # 坐标唯一性检查 (添加容差比较)
                    coordinate_exists = any(
                        abs(existing[0]-x_pos) < 1e-10 and 
                        abs(existing[1]-y_pos) < 1e-10 
                        for existing in points_data
                    )
                    if coordinate_exists:
                        continue
                        
                    points_data.append((x_pos, y_pos, y_speed))
                    x_set.add(x_pos)
                    y_set.add(y_pos)
                except (ValueError, IndexError):
                    continue
        
        if not points_data:
            print("错误：未找到有效数据点")
            return None, None, None, None
        
        # 创建有序坐标列表 (所有单位mm)
        x_coords = sorted(x_set)
        y_coords = sorted(y_set)
        self.x_coords = x_coords
        self.y_coords = y_coords
        
        # 坐标精度检查
        min_x = min(x_coords) if x_coords else 0
        min_y = min(y_coords) if y_coords else 0
        max_y = max(y_coords) if y_coords else 0
        print(f"原始数据范围 (单位mm): X: [{min_x:.6f}, {max(x_coords):.6f}], Y: [{min_y:.6f}, {max_y:.6f}]")
        if min_x < 1e-10 or min_y < 1e-10:
            print(f"警告：检测到接近零值坐标 (x_min={min_x:.6e}, y_min={min_y:.6e})")
        
        # === 1. 创建速度矩阵 ===
        speed_matrix_raw = np.full((len(y_coords), len(x_coords)), np.nan)
        dwell_matrix_raw = np.full((len(y_coords), len(x_coords)), np.nan)  # 原始网格的停留时间矩阵
        
        x_to_index = {x: idx for idx, x in enumerate(x_coords)}
        y_to_index = {y: idy for idy, y in enumerate(y_coords)}
        
        for x, y, speed in points_data:
            if x in x_to_index and y in y_to_index:
                idx_x = x_to_index[x]
                idx_y = y_to_index[y]
                speed_matrix_raw[idx_y, idx_x] = speed
                # 停留时间 = 1/速度 (单位秒)
                dwell_matrix_raw[idx_y, idx_x] = 1.0 / speed if abs(speed) > 1e-10 else np.nan
        
        # 填充速度和停留时间矩阵中的空缺值
        print("填充速度矩阵中的空白点...")
        speed_matrix = self.fill_matrix(speed_matrix_raw)
        
        # 重新计算停留时间矩阵，确保使用填充后的速度值
        dwell_matrix = np.full_like(speed_matrix, np.nan)
        valid_speed = speed_matrix > 1e-10  # 避免除以零错误
        dwell_matrix[valid_speed] = 1.0 / speed_matrix[valid_speed]
        
        # 应用镜像翻转 - 关键修改：只需翻转矩阵，不修改原始数据
        if self.mirror_y:
            print("应用Y轴镜像翻转...")
            # 垂直翻转矩阵（行方向）
            speed_matrix = np.flipud(speed_matrix)
            dwell_matrix = np.flipud(dwell_matrix)
            
            # 反转y坐标顺序，但保持矩阵对应关系
            y_coords = y_coords[::-1]
        
        # 保存速度矩阵
        self.speed_matrix = speed_matrix
        
        # === 2. 生成速度分布热力图和CSV ===
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # 为速度矩阵创建均匀网格坐标
        x_grid_speed = np.linspace(min(x_coords), max(x_coords), len(x_coords))
        
        # 关键修改：确保y坐标是翻转后的
        y_grid_speed = np.linspace(min(y_coords), max(y_coords), len(y_coords))
        self.x_grid = x_grid_speed
        self.y_grid = y_grid_speed
        
        # 应用圆形遮罩（如果需要）
        if self.circle_mode:
            speed_matrix = self.apply_circle_mask(speed_matrix, x_grid_speed, y_grid_speed)
            
        # 生成热力图
        speed_heatmap = os.path.join(output_dir, f"{base_name}_{'circular_' if self.circle_mode else ''}y_speed_heatmap{'_mirrored' if self.mirror_y else ''}.png")
        speed_csv = os.path.join(output_dir, f"{base_name}_y_speed_distribution{'_mirrored' if self.mirror_y else ''}.csv")
        
        self._generate_heatmap(
            speed_matrix, x_grid_speed, y_grid_speed, 
            speed_heatmap, speed_csv, 
            'Y-Speed (mm/s)', 
            cmap=self.circle_style if self.circle_mode else 'coolwarm',
            is_dwell_time=False,
            circle_mode=self.circle_mode
        )
        self.speed_heatmap_path = speed_heatmap
        
        # === 3. 创建1mm网格的停留时间分布 (单位mm) ===
        # 确定Y坐标的最小值和最大值（单位mm）
        min_y_val = min(y_coords)
        max_y_val = max(y_coords)
        
        # 创建1mm间隔的Y坐标网格 (单位mm)
        # 计算需要多少个点：从最小值到最大值，每1mm一个点
        num_points = int(np.ceil(max_y_val - min_y_val)) + 1
        y_coords_1mm = np.linspace(min_y_val, min_y_val + num_points - 1, num_points)
        self.y_coords_1mm = y_coords_1mm
        
        print(f"停留时间网格 (单位mm): Y范围: [{y_coords_1mm[0]:.6f}, {y_coords_1mm[-1]:.6f}], 点数={len(y_coords_1mm)}")
        
        # 创建新的停留时间矩阵（1mm网格，单位秒）
        dwell_matrix_1mm = np.full((len(y_coords_1mm), len(x_coords)), np.nan)
        
        # 对每一列(x位置)进行Y方向的插值 (使用原始网格)
        for col_idx, x_val in enumerate(x_coords):
            # 获取当前列的非NaN数据
            valid_mask = ~np.isnan(dwell_matrix[:, col_idx])
            valid_y = np.array(y_coords)[valid_mask]
            valid_dwell = dwell_matrix[valid_mask, col_idx]
            
            if len(valid_y) < 2:
                # 少于2个有效点，无法插值
                continue
                
            # 创建线性插值函数
            interp_fn = interp1d(
                valid_y, valid_dwell, 
                kind='linear', 
                bounds_error=False, 
                fill_value=np.nan
            )
            
            # 在当前列上进行插值到1mm网格
            dwell_matrix_1mm[:, col_idx] = interp_fn(y_coords_1mm)
            
            # 如果插值后仍有缺失，应用填充算法
            if np.isnan(dwell_matrix_1mm[:, col_idx]).any():
                # 需要将1D数组转换为2D矩阵以使用填充函数
                col_as_matrix = dwell_matrix_1mm[:, col_idx].reshape(-1, 1)
                filled_col = self.fill_matrix(col_as_matrix)
                dwell_matrix_1mm[:, col_idx] = filled_col.flatten()
        
        # 应用镜像翻转到插值后的停留时间矩阵
        if self.mirror_y:
            dwell_matrix_1mm = np.flipud(dwell_matrix_1mm)
        
        # 保存停留时间矩阵
        self.dwell_matrix = dwell_matrix_1mm
        
        # === 4. 生成停留时间分布热力图和CSV ===
        dwell_heatmap = os.path.join(output_dir, f"{base_name}_{'circular_' if self.circle_mode else ''}y_dwell_time_heatmap{'_mirrored' if self.mirror_y else ''}.png")
        dwell_csv = os.path.join(output_dir, f"{base_name}_y_dwell_time_distribution{'_mirrored' if self.mirror_y else ''}.csv")
        
        # 为停留时间矩阵创建均匀X网格坐标
        x_grid_dwell = np.linspace(min(x_coords), max(x_coords), len(x_coords))
        
        # 应用圆形遮罩（如果需要）
        if self.circle_mode:
            dwell_matrix_1mm = self.apply_circle_mask(dwell_matrix_1mm, x_grid_dwell, y_coords_1mm)
            
        self._generate_heatmap(
            dwell_matrix_1mm, x_grid_dwell, y_coords_1mm, 
            dwell_heatmap, dwell_csv, 
            'Dwell Time (s)', 
            cmap=self.circle_style if self.circle_mode else 'viridis',
            is_dwell_time=True,
            circle_mode=self.circle_mode
        )
        self.dwell_heatmap_path = dwell_heatmap
        
        return speed_heatmap, speed_csv, dwell_heatmap, dwell_csv

    def _generate_heatmap(self, matrix, x_coords, y_coords, image_path, csv_path, data_label, cmap, is_dwell_time=False, circle_mode=False):
        """生成热力图和CSV文件"""
        # 生成热力图
        fig = plt.figure(figsize=(10, 8))  # 使用正方形图像保证正圆
        
        if is_dwell_time:
            # 停留时间用对数色标，因为值可能差异很大
            norm = 'log' if np.nanmin(matrix) > 0 else None
        else:
            norm = None
        
        # 计算数据范围（忽略NaN）
        try:
            # 获取所有有效值
            valid_values = matrix[~np.isnan(matrix)]
            if valid_values.size > 0:
                vmin = np.min(valid_values)
                vmax = np.max(valid_values)
            else:
                vmin = 0
                vmax = 1
            
            # 确保值有效
            if np.isnan(vmin) or np.isinf(vmin):
                vmin = 0
            if np.isnan(vmax) or np.isinf(vmax):
                vmax = 1
            
            if vmin == vmax:
                vmin = 0
                vmax = 1
        except Exception as e:
            print(f"计算数据范围时出错: {str(e)}")
            vmin = 0
            vmax = 1
        
        # 热力图网格坐标
        X, Y = np.meshgrid(x_coords, y_coords)
        
        # 热力图绘图
        img = plt.pcolormesh(
            X, Y, matrix, 
            shading='auto', 
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            norm=norm
        )
        
        # 颜色条设置
        cbar = plt.colorbar(img, shrink=0.8)
        cbar_label = f'{data_label} ({vmin:.2e} to {vmax:.2e})'
        cbar.ax.set_ylabel(cbar_label, rotation=-90, va="bottom")
        
        if circle_mode:
            # 圆内显示样式
            title_label = f'{"Dwell Time" if is_dwell_time else "Y-Speed"} Distribution '
            title_label += f'(D={self.circle_diameter}mm)'
            
            # 添加镜像状态到标题
            if self.mirror_y:
                title_label += ' (Mirrored)'
            
            plt.title(title_label, fontsize=12, pad=12)
            
            # 添加圆形描边
            radius = self.circle_diameter / 2
            circle = plt.Circle((self.center_x, self.center_y), radius, 
                              color='white', fill=False, linewidth=1.5, linestyle='--')
            plt.gca().add_patch(circle)
            
            # 设置坐标轴范围（圆形区域内）
            plt.xlim(self.center_x - radius - 5, self.center_x + radius + 5)
            plt.ylim(self.center_y - radius - 5, self.center_y + radius + 5)
            
            # 关键修改：设置纵横比为1:1确保圆形正圆显示
            plt.gca().set_aspect('equal', adjustable='box')
        else:
            # 添加镜像状态到标题
            title_text = 'Dwell Time Distribution (1mm grid)' if is_dwell_time else 'Y-Speed Distribution'
            
            if self.mirror_y:
                title_text += ' (Mirrored)'
                
            plt.title(title_text, fontsize=12, pad=15)
        
        plt.xlabel('X-Position (mm)', fontsize=10)
        plt.ylabel('Y-Position (mm)', fontsize=10)
        
        # 设置科学计数法格式化
        plt.ticklabel_format(axis='both', style='sci', scilimits=(-3, 4))
        
        # 只在矩形模式下显示网格
        if not circle_mode:
            plt.grid(True, linestyle='--', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(image_path, dpi=150, bbox_inches='tight', pad_inches=0.1)
        plt.close(fig)
        
        # 生成CSV文件
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # CSV表头
            header_row = ['Y\X'] + [f"{x:.4f}" for x in x_coords]
            writer.writerow(header_row)
            
            # 数据行 - 行索引对应y坐标
            for i, y_val in enumerate(y_coords):
                row_data = [f"{y_val:.4f}"]  # Y坐标
                for j in range(len(x_coords)):
                    val = matrix[i, j]
                    if np.isnan(val):
                        row_data.append('NaN')
                    else:
                        # 智能格式化数值
                        if abs(val) < 0.001 or abs(val) > 1000:
                            row_data.append(f"{val:.4e}")
                        else:
                            row_data.append(f"{val:.6f}")
                writer.writerow(row_data)
        
        return image_path, csv_path

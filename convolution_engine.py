import numpy as np
import scipy.ndimage as ndi
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.colors import LogNorm
import csv
import os
import pandas as pd
import io

# 确保使用非交互式后端，适合在工作线程中使用
matplotlib.use('Agg')  # 使用Agg后端生成图像而不显示

class ConvolutionEngine:
    def __init__(self):
        # 初始化引擎变量
        self.dwell_matrix = None
        self.ion_beam_profile = None
        self.etch_depth_matrix = None
        self.x_coords = None
        self.y_coords = None
        
        # 圆形区域参数
        self.circle_mode = False
        self.circle_style = "jet"
        self.circle_diameter = 0
        self.center_x = 0
        self.center_y = 0
        
        # 镜像参数 (X轴镜像翻转)
        self.mirror_x = False
        
        # 记录最后一次计算使用的镜像状态
        self.last_mirror_state = False
    
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
    
    def load_dwell_time_matrix(self, file_path):
        """
        加载停留时间分布CSV文件（兼容RecipeEngine生成的1mm网格停留时间文件）
        """
        # 尝试使用pandas读取，兼容recipe_engine生成的文件格式
        try:
            df = pd.read_csv(file_path, index_col=0)
            # 提取x坐标
            y_coords = df.index.values.astype(float)
            x_coords = np.array([float(col) for col in df.columns])
            
            # 提取矩阵
            dwell_matrix = df.values
            
            return dwell_matrix, x_coords, y_coords
        except Exception as e:
            print(f"使用pandas加载停留时间文件失败: {str(e)}")
            return self._fallback_load_dwell_time(file_path)
    
    def _fallback_load_dwell_time(self, file_path):
        """后备方法加载停留时间文件"""
        # 读取原始CSV数据
        matrix_data = []
        x_coords = []
        y_coords = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                
                # 读取表头获取X坐标
                header = next(reader)
                # 跳过可能的说明行
                if header and header[0].strip().lower() == "coordinate (mm)":
                    try:
                        header = next(reader)  # 跳过第二行元数据行
                    except:
                        pass
                
                # 提取X坐标（跳过第一列）
                x_coords = [float(x.strip()) for x in header[1:] if x.strip()]
                
                # 读取数据行
                for row in reader:
                    if not row or not any(row):
                        continue
                        
                    # 第一列是Y坐标
                    try:
                        y_coord = float(row[0])
                    except ValueError:
                        continue
                        
                    y_coords.append(y_coord)
                    
                    # 提取数据值（跳过第一列）
                    row_data = []
                    for cell in row[1:]:
                        if not cell.strip():
                            continue
                        try:
                            # 尝试不同格式转换
                            if 'e' in cell.lower() or 'E' in cell:
                                value = float(cell)
                            else:
                                value = float(cell)
                            row_data.append(value)
                        except:
                            # 简单处理所有异常
                            row_data.append(np.nan)
                    matrix_data.append(row_data)
            
            return np.array(matrix_data), np.array(x_coords), np.array(y_coords)
        except Exception as e:
            print(f"后备方法加载停留时间文件失败: {str(e)}")
            # 创建空数组返回
            return np.array([]), np.array([]), np.array([])
    
    def apply_vertical_mirror(self, matrix, y_coords, center_y):
        """应用垂直镜像翻转并调整y坐标，保持中心点不变"""
        # 翻转矩阵
        flipped_matrix = np.flipud(matrix)
        
        # 计算翻转后的y坐标：保持中心点不变
        # 新的y坐标 = 2*center_y - 原始y坐标
        y_min = np.min(y_coords)
        y_max = np.max(y_coords)
        center = (y_min + y_max) / 2.0 if np.isnan(center_y) else center_y
        mirrored_y_coords = 2 * center - y_coords.copy()
        mirrored_y_coords = mirrored_y_coords[::-1]  # 反转顺序以匹配翻转后的矩阵
        
        return flipped_matrix, mirrored_y_coords, center
    
    def save_flipped_dwell_file(self, dwell_matrix, x_coords, y_coords, output_dir, base_name):
        """保存镜像翻转后的dwelltime文件"""
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        dwell_path = os.path.join(output_dir, f"{base_name}_dwell_mirrored.csv")
        
        try:
            with open(dwell_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # 写入表头
                header_row = ['Y\\X'] + [f"{x:.4f}" for x in x_coords]
                writer.writerow(header_row)
                
                # 写入数据行
                for i, y_val in enumerate(y_coords):
                    row_data = [f"{y_val:.4f}"]  # Y坐标
                    for j in range(len(x_coords)):
                        val = dwell_matrix[i, j]
                        if np.isnan(val):
                            row_data.append('NaN')
                        elif abs(val) < 0.001 or abs(val) > 1000:
                            row_data.append(f"{val:.4e}")
                        else:
                            row_data.append(f"{val:.6f}")
                    writer.writerow(row_data)
            return dwell_path
        except Exception as e:
            print(f"保存镜像翻转dwell文件失败: {str(e)}")
            return None
    
    def load_ion_beam_profile(self, file_path):
        """加载离子束能量分布profile"""
        matrix_data = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row or not any(row):
                        continue
                        
                    row_data = []
                    for cell in row:
                        if not cell.strip():
                            continue
                        try:
                            value = float(cell.strip())
                            row_data.append(value)
                        except ValueError:
                            continue
                    
                    if row_data:
                        matrix_data.append(row_data)
            
            return np.array(matrix_data)
        except Exception as e:
            print(f"加载离子束文件失败: {str(e)}")
            return np.array([])
    
    def convolve_matrix(self, dwell_matrix, ion_beam_profile):
        """执行离散卷积（累加）操作计算刻蚀深度"""
        if dwell_matrix.size == 0 or ion_beam_profile.size == 0:
            raise ValueError("输入矩阵尺寸无效")
            
        # 注意：卷积方向 - 离子束profile需要沿x和y轴翻转
        kernel = np.flipud(np.fliplr(ion_beam_profile))
        
        # 执行卷积操作
        # 使用same模式确保输出尺寸与输入相同
        etch_depth = ndi.convolve(
            dwell_matrix, 
            kernel, 
            mode='constant',
            cval=0.0
        )
        return etch_depth
    
    def generate_heatmap(self, matrix, x_coords, y_coords, output_dir, base_name, mirror_center=None):
        """
        生成刻蚀深度分布热力图
        添加 mirror_center 参数记录镜像中心
        """
        if matrix.size == 0:
            raise ValueError("蚀刻深度矩阵为空")
            
        # 使用原始矩阵和坐标创建可视化数据
        viz_matrix = matrix.copy()
        viz_y_coords = y_coords.copy()
        viz_x_coords = x_coords.copy()
        
        # 应用圆形遮罩（如果需要） - 只在可视化时应用
        if self.circle_mode:
            # 如果进行了镜像翻转，使用新的中心坐标
            applied_center_x = self.center_x
            applied_center_y = mirror_center if mirror_center is not None and self.last_mirror_state else self.center_y
            
            # 应用圆形遮罩
            viz_matrix = self.apply_circle_mask(viz_matrix, viz_x_coords, viz_y_coords)
        else:
            applied_center_x = None
            applied_center_y = None
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名后缀
        mirror_suffix = "_mirrored" if self.last_mirror_state else ""
        circle_suffix = "_circular" if self.circle_mode else ""
        
        # 图像文件名
        image_name = f"{base_name}{mirror_suffix}{circle_suffix}_etch_depth_heatmap.png"
        image_path = os.path.join(output_dir, image_name)
        
        # CSV文件名 - 只包含镜像后缀
        csv_name = f"{base_name}_etch_depth_distribution{mirror_suffix}.csv"
        csv_path = os.path.join(output_dir, csv_name)
        
        # ====================
        # 生成图像
        # ====================
        try:
            # 创建图形
            fig = plt.figure(figsize=(10, 8))
            
            # 计算数据范围（忽略NaN）
            if self.circle_mode:
                valid_matrix = viz_matrix[~np.isnan(viz_matrix)]
            else:
                valid_matrix = matrix[~np.isnan(matrix)] if np.any(~np.isnan(matrix)) else matrix
                
            if valid_matrix.size > 0:
                vmin = np.min(valid_matrix)
                vmax = np.max(valid_matrix)
            else:
                vmin = 0
                vmax = 1
            
            # 避免零范围
            if vmin == vmax:
                vmin -= 1e-3
                vmax += 1e-3
            
            # 使用对数归一化 (LogNorm来自matplotlib.colors)
            if vmin > 0 and vmax/vmin > 1000:
                norm = LogNorm(vmin=vmin, vmax=vmax)
            else:
                norm = None
            
            # 热力图网格坐标
            X, Y = np.meshgrid(viz_x_coords, viz_y_coords)
            
            # 热力图绘图
            cmap_name = self.circle_style if self.circle_mode else 'viridis'
            cmap = plt.get_cmap(cmap_name)
            img = plt.pcolormesh(
                X, Y, viz_matrix, 
                shading='auto', 
                cmap=cmap,
                vmin=vmin,
                vmax=vmax,
                norm=norm
            )
            
            # 颜色条设置
            cbar = plt.colorbar(img, shrink=0.8)
            cbar_min = np.min(valid_matrix)
            cbar_max = np.max(valid_matrix)
            cbar.set_label(f'Etch Depth (nm): [{cbar_min:.4e}, {cbar_max:.4e}]', rotation=90, labelpad=15)
            
            if self.circle_mode:
                # 从设置中获取圆心坐标
                center_x = applied_center_x if applied_center_x is not None else self.center_x
                center_y = applied_center_y if applied_center_y is not None else self.center_y
                
                # 圆内显示样式
                radius = self.circle_diameter / 2
                circle = plt.Circle((center_x, center_y), radius, 
                                  color='white', fill=False, linewidth=2, linestyle='--')
                plt.gca().add_patch(circle)
                
                # 设置坐标轴范围（圆形区域内）在圆形模式下
                plt.xlim(center_x - radius - 10, center_x + radius + 10)
                plt.ylim(center_y - radius - 10, center_y + radius + 10)
                
                # 设置纵横比确保圆形
                plt.gca().set_aspect('equal', adjustable='box')
                
                title = f"Etch Depth (D={self.circle_diameter}mm)"
            else:
                # 矩形模式下只添加标题和坐标轴标签
                title = "Etch Depth"
                
                # 如果没有应用圆形模式，则显示网格
                plt.grid(True, linestyle='--', alpha=0.3)
                
            # 添加镜像状态
            if self.last_mirror_state:
                title += " (Mirrored)"
            
            plt.title(title, fontsize=14, pad=12)
            plt.xlabel('X-Position (mm)', fontsize=10)
            plt.ylabel('Y-Position (mm)', fontsize=10)
            
            # 设置科学计数法格式化
            plt.ticklabel_format(axis='both', style='sci', scilimits=(-3, 4))
            
            # 保存图像
            plt.tight_layout()
            plt.savefig(image_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
        except Exception as e:
            print(f"生成图像失败: {str(e)}")
            # 创建错误图像
            plt.figure(figsize=(10, 8))
            plt.text(0.5, 0.5, f"图像生成错误:\n{str(e)}", 
                     ha='center', va='center', fontsize=12, color='red')
            plt.savefig(image_path)
            plt.close()
        
        # ====================
        # 生成CSV文件
        # ====================
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # CSV表头
                header_row = ['Y\\X'] + [f"{x:.4f}" for x in x_coords]
                writer.writerow(header_row)
                
                # 数据行 - 原始矩阵数据
                for i in range(len(y_coords)):
                    y_val = y_coords[i]
                    row_data = [f"{y_val:.4f}"]  # Y坐标
                    
                    for j in range(len(x_coords)):
                        val = matrix[i, j]
                        if np.isnan(val):
                            row_data.append('NaN')
                        elif abs(val) < 0.001 or abs(val) > 1000:
                            row_data.append(f"{val:.4e}")
                        else:
                            row_data.append(f"{val:.6f}")
                    
                    writer.writerow(row_data)
        except Exception as e:
            print(f"生成CSV文件失败: {str(e)}")
        
        return image_path, csv_path
    
    def process_etch_depth(self, dwell_time_csv, ion_beam_csv):
        """
        主处理函数：计算刻蚀深度分布
        返回: (heatmap_path, csv_path)
        """
        mirror_center = None
        
        try:
            # 加载停留时间分布
            dwell_matrix, x_coords, y_coords = self.load_dwell_time_matrix(dwell_time_csv)
            self.x_coords = x_coords
            self.y_coords = y_coords
            orig_y_coords = y_coords.copy()  # 保存原始y坐标用于镜像中心计算
            
            # 检查矩阵尺寸
            if dwell_matrix.size == 0 or len(x_coords) == 0 or len(y_coords) == 0:
                raise ValueError("停留时间数据无效")
            
            # 记录当前的镜像状态
            self.last_mirror_state = self.mirror_x
            
            # 应用镜像翻转 - 在这里执行翻转(重要!)
            if self.mirror_x:
                # 执行翻转操作（同时计算中心点）
                dwell_matrix, y_coords, mirror_center = self.apply_vertical_mirror(
                    dwell_matrix, 
                    y_coords,
                    self.center_y  # 使用用户设置的圆心
                )
                
                # 保存翻转后的dwell文件
                base_name = os.path.splitext(os.path.basename(dwell_time_csv))[0]
                output_dir = os.path.abspath("Data/convolution_results/")
                mirrored_dwell_path = self.save_flipped_dwell_file(
                    dwell_matrix, x_coords, y_coords, output_dir, base_name
                )
                print(f"已保存镜像翻转后的dwell文件: {mirrored_dwell_path}")
                print(f"镜像中心(Y坐标): {mirror_center}")
            
            # 替换NaN为0
            dwell_matrix = np.nan_to_num(dwell_matrix, nan=0.0)
            
            # 加载离子束profile
            ion_beam_profile = self.load_ion_beam_profile(ion_beam_csv)
            
            # 确保矩阵尺寸兼容
            if ion_beam_profile.size == 0:
                raise ValueError("离子束profile数据无效")
            
            # 执行卷积计算
            etch_depth = self.convolve_matrix(dwell_matrix, ion_beam_profile)
            
            # 保存结果
            base_name = os.path.splitext(os.path.basename(dwell_time_csv))[0]
            output_dir = os.path.abspath("Data/convolution_results/")
            
            # 生成图像和CSV（传递镜像中心）
            return self.generate_heatmap(etch_depth, x_coords, y_coords, output_dir, base_name, mirror_center)
        except Exception as e:
            # 即使出错也生成图像和CSV占位符
            base_name = os.path.splitext(os.path.basename(dwell_time_csv))[0]
            output_dir = os.path.abspath("Data/convolution_results/")
            os.makedirs(output_dir, exist_ok=True)
            
            # 错误图像路径
            image_path = os.path.join(output_dir, f"{base_name}_error.png")
            
            # 创建错误图像
            plt.figure(figsize=(10, 8))
            plt.text(0.5, 0.5, f"计算错误:\n{str(e)}", 
                     ha='center', va='center', fontsize=12, color='red')
            plt.savefig(image_path)
            plt.close()
            
            # 错误CSV路径
            csv_path = os.path.join(output_dir, f"{base_name}_error.csv")
            with open(csv_path, 'w') as f:
                writer = csv.writer(f)
                writer.writerow(['计算错误', str(e)])
                
            return image_path, csv_path

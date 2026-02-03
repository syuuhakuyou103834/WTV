import numpy as np
from scipy.spatial import cKDTree

def create_grid(x_min, x_max, y_min, y_max, resolution=200):
    return np.meshgrid(
        np.linspace(x_min, x_max, resolution),
        np.linspace(y_min, y_max, resolution)
    )

def calculate_data_bounds(data):
    if data is None or len(data) == 0:
        return -5, 5, -5, 5
    
    x_data = data[:,0]
    y_data = data[:,1]
    x_range = x_data.max() - x_data.min()
    y_range = y_data.max() - y_data.min()
    x_pad = x_range * 0.05 if x_range > 0 else 1.0
    y_pad = y_range * 0.05 if y_range > 0 else 1.0
    
    return (
        x_data.min() - x_pad,
        x_data.max() + x_pad,
        y_data.min() - y_pad,
        y_data.max() + y_pad
    )

def build_kd_tree(data):
    if data is None or len(data) == 0:
        return None, None
    return cKDTree(data[:, :2]), data[:, 2]

def calculate_quartiles(data):
    """计算指定数据的统计四分位数"""
    if data.size < 4:
        return {
            'max': np.max(data) if data.size > 0 else 0,
            'min': np.min(data) if data.size > 0 else 0,
            'q1': np.median(data) if data.size > 0 else 0,
            'median': np.median(data) if data.size > 0 else 0,
            'q3': np.median(data) if data.size > 0 else 0,
        }
    
    return {
        'max': np.max(data),
        'min': np.min(data),
        'q1': np.percentile(data, 25),
        'median': np.median(data),
        'q3': np.percentile(data, 75)
    }
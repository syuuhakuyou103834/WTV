import numpy as np
import os
import pandas as pd
from io import StringIO
from scipy.interpolate import griddata, RBFInterpolator
from scipy.spatial import cKDTree

def load_wafer_data(file_path):
    raw_lines = []
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                raw_lines = f.readlines()
            if raw_lines:
                break
        except (UnicodeError, IOError):
            continue

    if not raw_lines:
        raise ValueError("Unable to detect file encoding")

    file_ext = os.path.splitext(file_path)[1].lower()
    main_sep = ',' if file_ext == '.csv' else '\t'

    cleaned_data = []
    for i, line in enumerate(raw_lines):
        stripped_line = line.strip()
        if not stripped_line:
            continue

        stripped_line = stripped_line.rstrip(main_sep)
        parts = stripped_line.split(main_sep)[:3]
        if len(parts) < 3:
            continue
        cleaned_data.append(main_sep.join(parts))

    df = pd.read_csv(
        StringIO('\n'.join(cleaned_data)),
        sep=main_sep,
        engine='python',
        header=0 if len(cleaned_data) > 1 else None
    )

    df = df.iloc[:, :3]
    df.columns = ['x', 'y', 'thickness']
    df = df.apply(pd.to_numeric, errors='coerce').dropna()

    if len(df) < 3:
        raise ValueError("At least 3 valid data points required")

    return df.values, os.path.basename(file_path)

def process_data(data, wafer_size, extend_edge):
    x, y, z = data.T
    wafer_radius = wafer_size / 2
    
    # Calculate grid bounds
    if extend_edge:
        safety_factor = 1.05
        grid_range = wafer_radius * safety_factor
        x_min = y_min = -grid_range
        x_max = y_max = grid_range
    else:
        x_min, x_max = np.min(x) - wafer_radius*0.1, np.max(x) + wafer_radius*0.1
        y_min, y_max = np.min(y) - wafer_radius*0.1, np.max(y) + wafer_radius*0.1

    # Create grid
    grid_x, grid_y = np.meshgrid(
        np.linspace(x_min, x_max, 300),
        np.linspace(y_min, y_max, 300)
    )
    
    # Perform interpolation
    if extend_edge:
        try:
            rbf = RBFInterpolator(
                np.column_stack([x, y]),
                z,
                kernel='thin_plate_spline',
                neighbors=min(200, len(x)-1)
            )
            grid_z = rbf(np.column_stack([grid_x.ravel(), grid_y.ravel()])).reshape(grid_x.shape)
        except:
            grid_z = griddata((x, y), z, (grid_x, grid_y), method='linear')
    else:
        grid_z = griddata((x, y), z, (grid_x, grid_y), method='linear')
    
    # Apply wafer boundary mask
    distance = np.sqrt(grid_x**2 + grid_y**2)
    grid_z[distance > wafer_radius] = np.nan
    
    return grid_x, grid_y, grid_z

def calculate_statistics(data):
    if data is None or len(data) == 0:
        return {
            'count': 0,
            'max': 0,
            'min': 0,
            'mean': 0,
            'median': 0,
            'std': 0,
            'uniformity': 0
        }
    
    z = data[:, 2]
    # 确保有足够的数据点计算标准差
    if len(z) < 2:
        std_val = 0
    else:
        std_val = np.std(z, ddof=1)
        
    return {
        'count': len(data),
        'max': np.max(z),
        'min': np.min(z),
        'mean': np.mean(z),
        'median': np.median(z),
        'std': std_val, 
        'uniformity': (np.max(z) - np.min(z)) / np.mean(z) * 100
    }

def add_data_point(current_data, new_point, wafer_size):
    if current_data is None:
        return np.array([new_point])
    
    new_x, new_y, _ = new_point
    existing_idx = np.where(
        (np.abs(current_data[:,0] - new_x) < 1e-6) &
        (np.abs(current_data[:,1] - new_y) < 1e-6)
    )[0]
    
    if existing_idx.size > 0:
        current_data[existing_idx[0]] = new_point
        return current_data
    else:
        return np.vstack([current_data, new_point])

def delete_points(data, indices):
    sorted_indices = sorted(indices, reverse=True)
    for idx in sorted_indices:
        data = np.delete(data, idx, axis=0)
    return data

def modify_points(data, indices, new_value):
    data[indices, 2] = new_value
    return data

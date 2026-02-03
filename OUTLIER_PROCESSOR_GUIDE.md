# OutlierProcessor 使用指南

## 概述

`OutlierProcessor` 是一个强大的异常值处理器，专为晶圆膜厚数据优化设计。它可以智能地检测和移除异常数据点，以提高刻蚀模拟的均匀性。

## 主要功能

### 1. 异常值检测
- **IQR方法**：使用1.5倍四分位距检测异常值
- **增强检测**：支持多种检测方法（IQR、Z分数、修正Z分数）
- **数据质量验证**：自动检查数据完整性

### 2. 智能处理流程
- **分阶段处理**：先处理异常值，再处理最小值
- **用户交互**：支持用户确认是否继续处理
- **批量处理**：支持批量文件处理模式

### 3. 自动化功能
- **文件命名**：自动生成处理后的文件名
- **进度追踪**：记录处理轮次和移除的数据点
- **回调机制**：支持重新启动模拟

## 使用方法

### 基本使用

```python
from core.outlier_processor import OutlierProcessor

# 创建异常值处理器
processor = OutlierProcessor(
    etching_ui=self,              # EtchingSimulationUI实例
    main_window=main_window,       # 主窗口实例
    uniformity_threshold=5.0       # 均匀性阈值（%）
)

# 处理模拟完成结果
processor.handle_simulation_completed(results, unity_msg, validated_stats)
```

### 高级配置

```python
# 设置批量处理模式
processor.set_batch_mode(True)

# 设置模拟回调函数
processor.set_simulation_callback(self.restart_simulation_with_optimized_data)

# 验证数据质量
quality_result = processor.validate_data_quality(data)
if quality_result['valid']:
    print("数据质量良好")
else:
    print(f"数据质量问题: {quality_result['error']}")
```

## 异常值检测方法

### 1. IQR方法（默认）
```python
thickness_values = data[:, 2]
outlier_indices, lower_bound, upper_bound = processor._detect_outliers_1_5_iqr(thickness_values)
```

### 2. 增强检测方法
```python
# IQR方法
outlier_indices, info = processor.detect_outliers_enhanced(thickness_values, method='iqr')

# Z分数方法
outlier_indices, info = processor.detect_outliers_enhanced(thickness_values, method='zscore', z_threshold=2.0)

# 修正Z分数方法
outlier_indices, info = processor.detect_outliers_enhanced(thickness_values, method='modified_zscore')
```

## 处理流程

### 自动流程
1. **均匀性检查**：检查当前均匀性是否达标
2. **异常值检测**：使用IQR方法检测异常值
3. **异常值移除**：移除检测到的异常值
4. **重新模拟**：使用优化后的数据重新运行模拟
5. **最小值处理**：如果没有异常值但均匀性仍不达标，开始最小值删除
6. **循环处理**：重复直到均匀性达标或用户停止

### 手动控制
```python
# 单轮异常值处理
current_data = initial_data.copy()
outlier_indices, _, _ = processor._detect_outliers_1_5_iqr(current_data[:, 2])

if len(outlier_indices) > 0:
    # 移除异常值
    new_data, _ = processor._remove_outliers_and_save(current_data, outlier_indices, round_num)
else:
    # 移除最小值
    new_data, _ = processor._remove_min_values_and_save(current_data, removed_count, total_removed)
```

## 文件命名规则

### 异常值处理文件
- 第一次：`{原文件名}_outlier_removed.csv`
- 多轮次：`{原文件名}_outlier_round_{轮次}.csv`

### 最小值移除文件
- 第一次：`{原文件名}_min_removed.csv`
- 多轮次：`{原文件名}_min_removed_{数量}.csv`
- 组合：`{原文件名}_error_deleted_{轮次}_time_min_removed_{数量}.csv`

## 配置参数

```python
# 初始化参数
processor.min_data_points = 10              # 最少数据点数
processor.max_outlier_rounds = 20           # 最大异常值处理轮次
processor.data_retention_threshold = 0.3     # 最少保留30%的数据
processor.uniformity_threshold = 5.0         # 均匀性阈值（%）

# 批量处理参数
processor.batch_mode = False                 # 批量处理模式
processor.batch_progress_callback = callback   # 进度回调函数
```

## 与 EtchingSimulationUI 的集成

### 设置回调
```python
# 在 EtchingSimulationUI 中
self.outlier_processor = OutlierProcessor(self, self.main_window, self.uniformity_threshold)

# 设置重新模拟回调
self.outlier_processor.set_simulation_callback(self.restart_simulation_with_optimized_data)

# 处理模拟完成
self.outlier_processor.handle_simulation_completed(results, unity_msg, validated_stats)
```

### 重新模拟方法
```python
def restart_simulation_with_optimized_data(self, new_file_path, new_data):
    """使用优化后的数据重新启动模拟"""
    # 更新状态
    self.main_window.update_status_message(f"使用优化数据重新模拟...")

    # 增加模拟次数
    self.increment_simulation_count()

    # 创建新的模拟线程
    self.simulation_thread = SimulationThread(
        self.processor, new_file_path, self.beam_file, self.output_dir
    )

    # 连接信号并启动
    self.simulation_thread.results_ready.connect(self.on_optimized_simulation_completed)
    self.simulation_thread.start()
```

## 最佳实践

### 1. 数据质量检查
```python
# 在处理前验证数据
quality = processor.validate_data_quality(data)
if not quality['valid']:
    print(f"数据质量问题: {quality['error']}")
    return
```

### 2. 合理设置阈值
```python
# 根据实际需求设置均匀性阈值
uniformity_threshold = 3.0  # 高精度要求
# 或
uniformity_threshold = 5.0  # 标准要求
# 或
uniformity_threshold = 8.0  # 宽松要求
```

### 3. 监控处理进度
```python
# 跟踪处理统计信息
print(f"原始数据点: {processor.original_count}")
print(f"异常值轮次: {processor.outlier_rounds}")
print(f"最小值移除: {processor.min_removed_count}")
```

### 4. 批量处理优化
```python
# 批量处理时启用批量模式
processor.set_batch_mode(True)

# 设置进度回调
def update_progress(current, total, message):
    print(f"进度: {current}/{total} - {message}")

processor.set_batch_progress_callback(update_progress)
```

## 故障排除

### 常见问题

1. **数据点数不足**
   ```
   错误: 数据点数不足，最少需要10个点
   解决: 检查原始数据质量，确保有足够的数据点
   ```

2. **厚度数据异常**
   ```
   错误: 厚度数据包含NaN或无穷值
   解决: 清洗数据，移除或修复异常值
   ```

3. **坐标超出范围**
   ```
   错误: 坐标超出合理范围
   解决: 检查坐标系和单位，确保在晶圆范围内
   ```

### 调试技巧

1. **启用详细日志**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **检查处理历史**
   ```python
   print(f"优化历史: {processor.optimization_history}")
   print(f"用户选择历史: {processor.user_choice_history}")
   ```

3. **验证中间结果**
   ```python
   # 检查每轮处理后的数据
   def check_round_data(data, round_num):
       thickness_values = data[:, 2]
       print(f"第{round_num}轮 - 厚度统计:")
       print(f"  平均值: {np.mean(thickness_values):.2f}")
       print(f"  标准差: {np.std(thickness_values):.2f}")
       print(f"  范围: {np.min(thickness_values):.2f} - {np.max(thickness_values):.2f}")
   ```

## 示例代码

完整的使用示例请参考 `test_outlier_processor.py` 文件。

## 更新历史

- **v4.2.1** (2025-11-27)
  - 修复语法错误
  - 增强异常值检测方法
  - 添加数据质量验证
  - 改进批量处理支持
  - 优化用户交互体验
# ConvolutionEngine 功能与方法说明

## 1. 模块定位

`core/convolution_engine.py` 是 WTV 中的二维卷积计算与结果输出模块。它接收：

1. 一张带 x、y 坐标的 dwell-time（停留时间）二维网格；
2. 一张二维离子束强度或刻蚀能力 Profile；

然后通过离散二维卷积计算预测刻蚀深度分布，并输出坐标化 CSV 和热力图 PNG。

这个模块还负责以下辅助功能：

- dwell-time 的上下镜像以及镜像后坐标转换；
- 圆形晶圆区域的可视化遮罩；
- 线性或对数色标选择；
- 镜像 dwell-time 中间文件保存；
- 输入或计算失败时生成错误占位文件。

在当前业务链路中，它既服务于独立的“卷积积分”界面，也被 `IonBeamProcessor` 用作模拟刻蚀结果的卷积验算器。

## 2. 总体处理流程

```text
dwell-time CSV
    -> load_dwell_time_matrix()
    -> 可选 apply_vertical_mirror()
    -> NaN 替换为 0
                                  \
                                   -> convolve_matrix()
                                  /       |
ion-beam Profile CSV             /        v
    -> load_ion_beam_profile()       etch-depth 矩阵
                                             |
                                             v
                                    generate_heatmap()
                                      |            |
                                      v            v
                                     PNG          CSV
```

端到端入口是 `process_etch_depth()`，正常情况下返回：

```python
(heatmap_path, csv_path)
```

## 3. 核心数据与对象状态

`ConvolutionEngine` 是有状态对象。当前类中主要属性如下：

| 属性 | 默认值 | 作用 |
| --- | --- | --- |
| `dwell_matrix` | `None` | 预留的 dwell 矩阵状态；当前流程没有回写该属性 |
| `ion_beam_profile` | `None` | 预留的 Beam Profile 状态；当前流程没有回写该属性 |
| `etch_depth_matrix` | `None` | 预留的刻蚀深度状态；当前流程没有回写该属性 |
| `x_coords` | `None` | 最近一次读取的 dwell x 坐标 |
| `y_coords` | `None` | 最近一次读取的原始 dwell y 坐标 |
| `circle_mode` | `False` | 是否在热力图中仅显示圆形区域 |
| `circle_style` | `"jet"` | 圆形模式下使用的 Matplotlib colormap |
| `circle_diameter` | `0` | 圆形区域直径，界面中按 mm 输入 |
| `center_x` | `0` | 圆心 x 坐标 |
| `center_y` | `0` | 圆心或镜像中心 y 坐标 |
| `mirror_x` | `False` | 是否执行上下翻转，即关于水平轴的镜像 |
| `last_mirror_state` | `False` | 最近一次计算实际采用的镜像状态，用于输出命名和标题 |

脚本通过 `matplotlib.use('Agg')` 选择非交互式后端，目的是允许工作线程在不打开 Matplotlib 窗口的情况下生成 PNG。

## 4. 输入文件格式

### 4.1 Dwell-time CSV

首选读取方式是：

```python
pd.read_csv(file_path, index_col=0)
```

约定格式为：

```text
Y\X, x0, x1, x2, ...
y0, value, value, value, ...
y1, value, value, value, ...
...
```

- 第一行除首格外是 x 坐标；
- 第一列除首格外是 y 坐标；
- 其余区域构成 dwell-time 矩阵；
- Pandas 读取失败时，代码会调用 `_fallback_load_dwell_time()` 手动解析。

后备解析支持第一格为 `Coordinate (mm)` 的说明格式，也会把无法转换的数值写成 `NaN`。正常主流程在卷积前把所有 `NaN` 替换为 `0.0`。

### 4.2 Ion Beam Profile CSV

Beam Profile 不包含坐标表头，所有可解析的数值直接组成二维矩阵：

```text
value, value, value, ...
value, value, value, ...
...
```

- 空行被跳过；
- 空单元格被跳过；
- 无法转换成浮点数的单元格也被跳过；
- 文件使用 UTF-8 读取，无法解码的字符被忽略。

当前代码只检查矩阵是否为空，没有强制要求 Profile 必须为固定尺寸。不过项目中的典型 Beam Profile 是 31 x 31。

## 5. 核心数学过程

### 5.1 圆形遮罩

给定圆心 `(center_x, center_y)` 和直径 `diameter`，半径为：

```text
radius = diameter / 2
```

网格点到圆心的距离为：

```text
distance = sqrt((X - center_x)^2 + (Y - center_y)^2)
```

满足 `distance <= radius` 的点保留，圆外数据设为 `NaN`。

需要特别注意：当前圆形遮罩只应用于热力图的 `viz_matrix`。输出的刻蚀深度 CSV 始终保存未遮罩的完整矩阵，因此圆形模式是显示模式，不是数值裁剪模式。

### 5.2 上下镜像与坐标转换

矩阵通过以下操作上下翻转：

```python
flipped_matrix = np.flipud(matrix)
```

镜像中心优先使用传入的 `center_y`；只有 `center_y` 是 `NaN` 时，才自动使用 y 坐标范围中点：

```text
center = (min(y) + max(y)) / 2
```

镜像后的坐标为：

```text
y_mirrored = 2 * center - y_original
```

坐标数组随后反序，以保持与翻转后矩阵的行顺序一致。界面中将这一操作描述为“沿 X 轴镜像翻转”，因为它改变上下方向和 y 坐标，x 坐标保持不变。

### 5.3 二维卷积

代码首先把 Beam Profile 沿 x、y 两个方向翻转，相当于旋转 180°：

```python
kernel = np.flipud(np.fliplr(ion_beam_profile))
```

然后执行：

```python
etch_depth = scipy.ndimage.convolve(
    dwell_matrix,
    kernel,
    mode="constant",
    cval=0.0,
)
```

当前实现的关键特征：

- 输出矩阵尺寸与 dwell-time 矩阵相同；
- 边界外数据按 0 处理；
- Beam Profile 不做归一化；
- 不显式乘坐标步长或像素面积；
- dwell 中的 `NaN` 在卷积前变为 0；
- Profile 的朝向由显式 180° 翻转和 `ndi.convolve` 的定义共同决定。

如果 dwell-time 单位为秒、Beam Profile 数值单位为 `nm/s`，离散累加结果可以解释为 `nm`。代码和输出标签采用 `Etch Depth (nm)`，但模块本身不会检查输入单位。

## 6. 各方法作用

### `__init__()`

初始化计算状态、圆形显示参数和镜像开关。当前真正参与流程的是坐标、圆形参数、`mirror_x` 和 `last_mirror_state`；三个矩阵属性目前只是预留字段。

### `set_circle_params(diameter, center_x, center_y)`

保存圆形区域的直径和圆心。该方法不启用圆形模式，`circle_mode` 由界面单独设置。

### `create_circle_mask(X, Y, center_x, center_y, diameter)`

根据二维坐标网格计算布尔圆形遮罩。圆内和圆周为 `True`，圆外为 `False`。

### `apply_circle_mask(matrix, x_coords, y_coords)`

通过 `np.meshgrid()` 构造坐标网格，调用 `create_circle_mask()`，复制输入矩阵，并把圆外元素改成 `NaN`。输入矩阵尺寸应与 `(len(y_coords), len(x_coords))` 一致。

### `load_dwell_time_matrix(file_path)`

使用 Pandas 读取带坐标的 dwell-time CSV：

- DataFrame 列名转成 x 坐标；
- DataFrame index 转成 y 坐标；
- DataFrame values 作为 dwell 矩阵。

Pandas 解析失败时打印错误并转入后备解析。返回：

```python
(dwell_matrix, x_coords, y_coords)
```

### `_fallback_load_dwell_time(file_path)`

用标准库 `csv` 手动解析 dwell 文件。它负责提取表头坐标、逐行读取 y 坐标及矩阵值，并在失败时返回三个空数组。

这是兼容性路径，不是当前标准 RecipeEngine 输出的主要读取路径。

### `apply_vertical_mirror(matrix, y_coords, center_y)`

执行矩阵上下翻转，同时围绕指定 y 中心变换 y 坐标。返回：

```python
(flipped_matrix, mirrored_y_coords, actual_center)
```

### `save_flipped_dwell_file(...)`

将镜像后的 dwell 矩阵保存到：

```text
<base_name>_dwell_mirrored.csv
```

首行写 x 坐标、首列写 y 坐标。数值根据大小选择科学计数法或 6 位小数；`NaN` 写成字符串 `NaN`。保存失败时返回 `None`。

### `load_ion_beam_profile(file_path)`

读取无坐标表头的二维 Beam Profile，提取所有可转换的浮点数并构造 NumPy 数组。失败时打印原因并返回空数组。

### `convolve_matrix(dwell_matrix, ion_beam_profile)`

验证两个矩阵非空，将 Profile 旋转 180°，再调用 `scipy.ndimage.convolve()` 计算刻蚀深度矩阵。输入为空时抛出 `ValueError`。

### `generate_heatmap(matrix, x_coords, y_coords, output_dir, base_name, mirror_center=None)`

同时生成 PNG 与 CSV，是输出逻辑的主体。

PNG 处理包括：

- 可选圆形遮罩；
- 忽略 `NaN` 计算色标范围；
- 当全部有效值为正且动态范围大于 1000 倍时尝试使用 `LogNorm`；
- 圆形模式使用用户指定 colormap，矩形模式固定使用 `viridis`；
- 圆形模式绘制白色虚线边界并保持等比例坐标轴；
- 镜像模式在标题和文件名中加入 `Mirrored`；
- 图片以 150 DPI 输出。

CSV 处理包括：

- 首行写 x 坐标，首列写 y 坐标；
- 保存完整、未应用圆形遮罩的原始刻蚀深度矩阵；
- `NaN` 写为 `NaN`；
- 很小或大于 1000 的值采用科学计数法，其余保留 6 位小数。

即使 PNG 生成失败，方法也会创建一张包含错误文字的 PNG；CSV 失败则只打印错误。最后仍返回预定的两个路径。

### `process_etch_depth(dwell_time_csv, ion_beam_csv)`

端到端主入口，执行顺序如下：

1. 读取 dwell 矩阵及坐标；
2. 保存最近一次原始 x、y 坐标；
3. 检查 dwell 数据非空；
4. 记录本次镜像状态；
5. 可选执行上下镜像，并保存镜像 dwell CSV；
6. 将 dwell 中的 `NaN` 替换为 0；
7. 读取 Beam Profile；
8. 检查 Profile 非空；
9. 执行二维卷积；
10. 在 `Data/convolution_results/` 生成结果文件。

如果任意步骤发生异常，该方法不会继续向调用方抛出异常，而是生成：

```text
<base_name>_error.png
<base_name>_error.csv
```

然后同样返回这两个错误占位文件的路径。

## 7. 输出文件命名

正常输出目录由当前进程工作目录决定：

```text
Data/convolution_results/
```

| 场景 | PNG | CSV |
| --- | --- | --- |
| 普通 | `<base>_etch_depth_heatmap.png` | `<base>_etch_depth_distribution.csv` |
| 镜像 | `<base>_mirrored_etch_depth_heatmap.png` | `<base>_etch_depth_distribution_mirrored.csv` |
| 圆形 | `<base>_circular_etch_depth_heatmap.png` | `<base>_etch_depth_distribution.csv` |
| 镜像且圆形 | `<base>_mirrored_circular_etch_depth_heatmap.png` | `<base>_etch_depth_distribution_mirrored.csv` |
| 失败 | `<base>_error.png` | `<base>_error.csv` |

圆形后缀只出现在 PNG，因为 CSV 保存的始终是完整矩阵。相同输入文件名再次计算会覆盖旧输出。

## 8. 在 WTV 中的调用关系

### `ui/convolution_integral_ui.py`

界面持有一个 `ConvolutionEngine` 实例，并允许用户：

- 选择 dwell-time 和 Beam Profile 文件；
- 开关圆形显示；
- 设置圆直径、圆心和 colormap；
- 开关沿 X 轴镜像；
- 在 `QThread` 中调用 `process_etch_depth()`；
- 计算完成后加载并显示 PNG。

工作线程只把 PNG 路径和状态文字发回界面，CSV 路径没有直接显示给用户。

### `core/etching_processor.py`

`IonBeamProcessor.convolve_dwell_time()` 会把内部 dwell-time 和 Beam Profile 临时保存成 CSV，调用本引擎，再读取结果 CSV。该结果用于：

- 与目标刻蚀深度图比较；
- 计算晶圆内部的最小值、最大值、平均值；
- 计算模拟结果与目标结果的 MSE。

因此该引擎不仅负责图片展示，也参与刻蚀优化流程的结果验算。

## 9. 当前默认数据验证基准

使用项目根目录中的以下文件进行只读计算：

```text
Base_Recipe_auto_21-2301_y_dwell_time_distribution.csv
ion_beam_profile.csv
```

当前结果为：

| 指标 | 结果 |
| --- | ---: |
| dwell 矩阵 | 179 x 180 |
| x 范围 | -40.5 到 138.5，共 180 点 |
| y 范围 | 22.62 到 200.62，共 179 点 |
| dwell 中 NaN 数 | 358 |
| dwell 非 NaN 范围 | 0.007849 到 0.020383 |
| Beam Profile | 31 x 31 |
| Beam Profile 范围 | 0 到 264.794853605203 |
| Beam Profile 总和 | 6473.443959629525 |
| 卷积输出 | 179 x 180 |
| 刻蚀深度范围 | 17.924143174079948 到 117.4525493431736 |
| 刻蚀深度矩阵总和 | 2661150.3187331604 |

该结果没有写出文件，可作为后续重构卷积算法时的数值回归基线。

## 10. 当前实现的假设与升级注意点

以下是当前真实行为，后续修改时应明确是否保持兼容：

1. dwell 主读取路径依赖首列为 y 坐标、表头其余列为 x 坐标。
2. 后备解析遇到 `Coordinate (mm)` 时会把下一行当成新表头，需确认是否完全符合所有历史文件格式。
3. 后备 dwell 解析和 Beam Profile 解析会跳过空单元格，可能造成行长度不一致。
4. 主流程只检查数组非空，没有显式验证矩阵、x 坐标和 y 坐标的尺寸一致性。
5. dwell 中缺失值直接按 0 参与卷积；输入中的正负无穷值没有业务级校验。
6. Profile 没有归一化，输出量级直接依赖 Profile 原始标定。
7. 卷积没有乘空间采样间距，因此默认把每个网格单元视为等权离散样本。
8. 边界使用零填充，靠近矩阵边缘的刻蚀深度会受到截断效应影响。
9. `mirror_x` 实际翻转矩阵行和 y 坐标，名称表示“关于 X 轴镜像”，不是翻转 x 列。
10. 当界面圆心 y 默认为 0 时，镜像围绕 y=0，而不是自动围绕数据范围中点。
11. 圆形模式只改变 PNG，不改变卷积输入和输出 CSV。
12. 动态范围很大时同时传入 `LogNorm`、`vmin` 和 `vmax`，需要针对当前 Matplotlib 版本验证兼容性。
13. `matplotlib.use('Agg')` 位于 `pyplot` 导入之后，严格来说后端选择最好在导入 `pyplot` 前完成。
14. `process_etch_depth()` 把异常转换成错误文件，因此上层线程通常仍会收到“finished”而不是“error”信号。
15. 输出目录基于当前工作目录，而不是脚本位置或统一资源路径。
16. 同名输入会覆盖已有输出，没有时间戳或版本号。
17. `dwell_matrix`、`ion_beam_profile`、`etch_depth_matrix` 和 `orig_y_coords` 当前没有被后续逻辑使用。
18. `matplotlib.cm` 和 `io` 当前是未使用导入。

## 11. 方法速查表

| 方法 | 主要职责 | 返回值 |
| --- | --- | --- |
| `__init__()` | 初始化引擎状态和显示参数 | 无 |
| `set_circle_params()` | 设置圆直径和圆心 | 无 |
| `create_circle_mask()` | 计算圆形布尔遮罩 | `mask` |
| `apply_circle_mask()` | 将矩阵圆外区域设为 NaN | `masked_matrix` |
| `load_dwell_time_matrix()` | 用 Pandas 读取 dwell 网格 | `matrix, x, y` |
| `_fallback_load_dwell_time()` | 手动兼容读取 dwell 网格 | `matrix, x, y` |
| `apply_vertical_mirror()` | 翻转矩阵并转换 y 坐标 | `matrix, y, center` |
| `save_flipped_dwell_file()` | 保存镜像 dwell CSV | 路径或 `None` |
| `load_ion_beam_profile()` | 读取 Beam Profile | 二维数组 |
| `convolve_matrix()` | 执行离散二维卷积 | 刻蚀深度矩阵 |
| `generate_heatmap()` | 输出热力图和坐标化 CSV | `image_path, csv_path` |
| `process_etch_depth()` | 执行完整计算流程 | `image_path, csv_path` |

---

本文档依据当前 `core/convolution_engine.py`、`ui/convolution_integral_ui.py` 和 `core/etching_processor.py` 的实际实现编写，描述的是现有版本行为。

# WedgeTestResult Analyzer 功能与实现原理

## 1. 模块定位

`wedgeTestResult_analyzer.py` 是 WedgeMaster 的核心标定模块。它把三类数据关联起来：

1. WedgeTest Recipe 中每个扫描点的位置与 `vy` 参数；
2. 刻蚀前、刻蚀后的膜厚测量结果；
3. 可选的二维 Beam Profile。

模块首先根据膜厚差计算每个测量点的实际去除量，然后将去除量配准到 Recipe 的扫描点，建立“`1 / vy` 与实际去除量”的过原点线性关系。回归斜率用于计算 Beam Peak，并可进一步归一化二维 Beam Profile、计算其沿 y 方向的离散积分。

从业务角度看，这个模块完成的是：**利用一次 Wedge Test 的实测去除结果，反推出扫描参数与束流去除能力之间的标定系数。**

## 2. 对象状态与数据模型

`WedgeTestAnalyzer` 是有状态对象，主要保存以下数据：

| 属性 | 内容 |
| --- | --- |
| `map_wtr` | Recipe 原始 WTR 坐标系的 95 x 95 点阵 |
| `map_tm` | 以 Recipe 中心为原点、y 轴反向后的 TM 坐标点阵 |
| `map_wf` | 根据前后膜厚差生成的 WF 稀疏测量网格 |
| `wtr_center` | WTR 坐标范围中心点 |
| `coord_tolerance` | 坐标匹配容差，固定为 `0.001` |
| `beam_peak` | 由回归斜率和用户系数 `k` 计算出的 Beam Peak |

正确的调用顺序具有依赖关系：

```text
load_recipe()
    -> 生成 map_wtr、wtr_center、map_tm

load_thickness()
    -> 生成 map_wf

transfer_trimming_amount()
    -> 将 map_wf 的去除量写入 map_tm

calculate_slope()
    -> 得到回归斜率

calculate_beam_peak(k)
    -> 得到 Beam Peak

process_beam_profile()                 可选
    -> 生成按 Beam Peak 缩放的新 Profile

calculate_beam_y_integration()         可选
    -> 得到一维积分曲线和总积分
```

## 3. 输入数据契约

### 3.1 WedgeTest Recipe

Recipe CSV 的有效数据行必须严格为 `95 x 95 = 9025` 行，每行必须恰好有 5 列：

| CSV 列 | 代码中的含义 |
| --- | --- |
| A | 序号，不写入点阵 |
| B | `x`，WTR x 坐标 |
| C | `vx`，当前只存入 `map_wtr`，后续计算未使用 |
| D | `y`，WTR y 坐标 |
| E | `vy`，回归计算使用的参数 |

读取时有两条特殊过滤规则：

- A 列字符串等于 `"1"` 的行被视为首行并跳过；
- B、C、D、E 四列都等于 0 的行被视为末行并跳过。

过滤后若不是 9025 行，模块立即抛出异常。数据按 CSV 当前行顺序逐行填入 95 x 95 数组，代码不会额外校验坐标排序是否符合预期。

### 3.2 初始与刻蚀后膜厚

两个 CSV 都跳过第一行表头，随后读取前三列：

```text
X, Y, Thickness
```

坐标被四舍五入到小数点后 3 位。实际去除量定义为：

```text
Trimming Amount = Initial Thickness - After Thickness
```

当前默认数据的 Thickness 表头标记单位为 `nm`，因此在这组数据中去除量也是 `nm`。模块本身没有强制检查或换算单位。

### 3.3 Beam Profile

Beam Profile CSV 中每个单元格都会尝试转换成浮点数；无法转换的内容被替换成 `0.0`。

- Profile 缩放阶段没有先强制检查尺寸；
- y 方向积分阶段严格要求数组为 `31 x 31`；
- 31 列被映射为 x 坐标 `-15` 到 `+15 mm`，步长为 `1 mm`。

## 4. 核心算法

### 4.1 从 WTR 坐标转换到 TM 坐标

Recipe 中心不是取某个指定点，而是由坐标极值的包围盒中心计算：

```text
center_x = (max(x_wtr) + min(x_wtr)) / 2
center_y = (max(y_wtr) + min(y_wtr)) / 2
```

每个点的 TM 坐标为：

```text
x_tm = x_wtr - center_x
y_tm = center_y - y_wtr
```

因此 x 轴只平移，y 轴在平移的同时反向。这一步把 Recipe 坐标转换成以中心为原点、方向与膜厚测量网格一致的坐标。

### 4.2 建立 WF 去除量网格

代码从 initial 文件中提取唯一 x、y 坐标并排序，用最小值、最大值和唯一坐标数量推算固定步长，然后生成完整笛卡尔网格。

对每个网格点 `(x, y)`：

```text
map_wf[x][y] = initial[x, y] - after[x, y]
```

若某个坐标在 initial 或 after 中不存在，该侧厚度会以 `0` 代替。

### 4.3 将 WF 去除量配准到 TM 点阵

代码遍历 9025 个 TM 点，在 WF 网格中寻找同时满足以下条件的坐标：

```text
abs(wf_x - x_tm) < 0.001
abs(wf_y - y_tm) < 0.001
```

匹配成功时，将 WF 去除量写入对应 TM 点的 `trimming_amount`；未匹配的点保持 `None`。

### 4.4 过原点线性回归

只有满足以下全部条件的点才进入回归：

- `trimming_amount` 已成功匹配；
- `trimming_amount != 0`；
- `vy != 0`。

对每个有效点定义：

```text
x_i = 1 / vy_i
y_i = trimming_amount_i
```

模型固定为过原点直线：

```text
y = slope * x
```

最小二乘斜率直接计算为：

```text
slope = sum(x_i * y_i) / sum(x_i^2)
```

代码要求至少有两个有效点。它不计算截距、R²、置信区间、残差或异常值，也不对不同测量点设置权重。

`get_regression_data()` 和 `export_regression_data()` 使用完全相同的有效点筛选规则。导出文件固定为：

```text
Data/outputs/Regression_Data/regression_data.csv
```

### 4.5 Beam Peak

用户界面提供系数 `k`，默认值为 `1.0`：

```text
Beam Peak = k * slope
```

`k` 在核心模块中没有范围限制或物理单位检查。

### 4.6 Beam Profile 归一化

原始 Profile 的最大值记为 `profile_max`。当 `profile_max > 0` 时：

```text
scaling_factor = Beam Peak / profile_max
new_profile = original_profile * scaling_factor
```

这样缩放后 Profile 的最大值等于 Beam Peak，同时保留原 Profile 的相对二维形状。输出保留 8 位小数，默认保存为：

```text
Data/outputs/new_BeamShapeProfile/New_<原文件名>
```

### 4.7 Beam Profile 沿 y 方向积分

对于 31 x 31 Profile，代码按列求和：

```text
y_integration[x_j] = sum(profile[:, j])
total_integration = sum(y_integration)
```

返回结果为：

1. x 坐标列表 `[-15, -14, ..., 15]`；
2. 31 个按列求和结果；
3. 全部 961 个单元格的总和。

这里实现的是离散求和，没有显式乘以空间步长；由于当前假定步长为 `1 mm`，数值上与乘以 1 相同，但物理单位仍需要由上层业务定义。

## 5. 与界面的实际衔接

`ui/analyzer_ui.py` 的“执行分析”按钮按以下顺序调用本模块：

1. 读取用户输入的 `k`；
2. 加载 Recipe；
3. 加载前后膜厚；
4. 配准实际去除量；
5. 计算并显示斜率及回归散点图；
6. 可选导出回归点；
7. 计算并显示 Beam Peak；
8. 可选缩放 Beam Profile、计算积分并绘制一维曲线；
9. 将 slope、Beam Peak、Beam integration 和相关系数写入 WedgeTest 日志。

界面中绘制的趋势线同样使用 `y = slope * x`，与核心模块的过原点回归保持一致。

## 6. 当前默认数据的验证基准

使用 2026-07-18 项目目录中的默认文件执行当前代码，得到：

| 指标 | 当前结果 |
| --- | ---: |
| Recipe 有效点阵 | 95 x 95，共 9025 点 |
| WTR 中心 | `(43.25, 131.56)` |
| WF 测量网格 | 21 x 21，共 441 点 |
| 成功配准到 TM 的点 | 441 |
| 进入回归的有效点 | 381 |
| 过原点回归斜率 | `3384.269285907028` |
| 当 `k = 1.0` 时的 Beam Peak | `3384.269285907028` |

该结果可作为后续升级前的回归测试基线。任何算法调整都应说明是否预期改变上述点数或斜率。

## 7. 当前实现中的关键假设与风险

这些内容不一定都是错误，但升级时必须明确是否继续保留：

1. Recipe 必须固定为 95 x 95，且依赖 CSV 行顺序，不验证二维坐标拓扑。
2. A 列等于 `1` 的任意行都会被跳过，并不只检查文件物理首行。
3. B 到 E 全零的任意行都会被跳过，并不只检查文件物理末行。
4. WF 网格步长由 initial 文件推算，默认坐标均匀且至少各有两个唯一值。
5. initial 或 after 缺失的坐标以厚度 0 参与相减，可能制造非真实去除量。
6. 坐标先保留 3 位小数，再使用严格小于 `0.001` 的容差匹配。
7. 未匹配点、零去除量点和 `vy = 0` 点直接排除，没有统计原因分类。
8. 回归被强制通过原点，没有拟合优度、异常值处理和不确定度评估。
9. `vx` 被读取但完全没有参与当前算法。
10. Beam Profile 中无法解析的内容静默替换为 0，可能掩盖输入格式问题。
11. Profile 缩放阶段不验证 31 x 31，直到积分阶段才检查尺寸。
12. 回归数据和同名 New Profile 会覆盖已有输出文件。
13. 类依赖严格调用顺序，但方法本身只对部分前置状态做显式检查。

## 8. 后续升级时建议优先明确的问题

在修改算法前，最好先确认以下业务定义：

- `vy` 的物理含义、单位，以及使用 `1 / vy` 的理论依据；
- 回归是否必须经过原点，是否需要截距、R²、残差和异常值策略；
- 膜厚坐标与 TM 坐标的容差、插值和缺失点规则；
- 固定 95 x 95 Recipe 与 21 x 21 膜厚网格是否仍是长期约束；
- `k` 的来源，以及 Beam Peak、Beam integration 的预期物理单位；
- Beam Profile 的坐标方向、采样间距与积分是否需要乘实际面积元素；
- 是否需要保留当前结果作为兼容模式，并增加新版算法模式。

## 9. 方法职责速查

| 方法 | 主要职责 | 关键输出或副作用 |
| --- | --- | --- |
| `load_recipe()` | 读取并验证 Recipe | `map_wtr`、`wtr_center`、`map_tm` |
| `_generate_tm_mapping()` | WTR 转 TM 坐标 | 95 x 95 `map_tm` |
| `load_thickness()` | 计算前后膜厚差 | `map_wf` |
| `_read_thickness_file()` | 读取三列膜厚 CSV | `{(x, y): thickness}` |
| `transfer_trimming_amount()` | WF 与 TM 坐标匹配 | 写入 `trimming_amount` |
| `calculate_slope()` | 过原点最小二乘回归 | `slope` |
| `get_regression_data()` | 获取绘图数据 | `x_data, y_data` |
| `export_regression_data()` | 导出回归点 | `regression_data.csv` |
| `calculate_beam_peak()` | 应用用户系数 | `beam_peak = k * slope` |
| `process_beam_profile()` | 将 Profile 峰值归一到 Beam Peak | 新 Profile CSV |
| `calculate_beam_y_integration()` | 对 31 x 31 Profile 按列求和 | x、积分曲线、总积分 |

---

本文档依据当前 `core/wedgeTestResult_analyzer.py` 与其在 `ui/analyzer_ui.py` 中的实际调用方式编写，描述的是现有版本行为，而不是理想化设计。

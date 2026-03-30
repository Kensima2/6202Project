# Configs 参数指南

本指南说明 `configs/` 下各配置文件的用途、关键参数及修改方法。

---

## 📋 配置文件概览

| 文件 | 用途 | 应用场景 |
|------|------|---------|
| `litho_config_scan.json` | 光刻工艺参数 | 光刻仿真（单晶圆） |
| `litho_config_pipeline.json` | 光刻流程配置 | 7层工艺流程中的POLY步骤 |
| `process_flow.json` | 完整工艺流程配置 | 7层工艺（GDS→POLY→蚀刻→注入→金属→设备） |
| `layer_map.json` | GDS图层-工艺层映射 | GDS文件导入，定义层号对应 |
| `*_example.json` | 配置示例 | 参考用，勿修改 |


---

## 1. litho_config_scan.json （光刻扫描配置）

用于 `01_lithography/run_project.py` 的光刻仿真与工艺窗口计算。

---

### 核心参数详解


#### 目标与公差参数

**`target_cd_nm`** - 目标线宽（CD，Critical Dimension）
- **含义**：工艺节点的特征尺寸
- **典型值**：45 nm
- **代码背景**：在 `photolithography_baseline.py` 中定义，用于 CD提取和过程窗口判决
- **注意**：值域需要与 pitch_nm 和 duty_cycle 匹配

---

**`cd_tol_nm`** - CD公差
- **含义**：允许偏差范围（±值），定义工艺通过/失败的判定标准
- **典型值**：5 nm
- **合格范围**：[target_cd_nm - cd_tol_nm, target_cd_nm + cd_tol_nm]
- **应用**：工艺窗口中的绿色区域面积通过此阈值判定

---

#### 图案与掩膜参数

**`pattern`** - 图案类型
- **选项**：`"line_space_1d"` | `"contact_2d"`
- **默认值**：line_space_1d
- **含义**：
  - `"line_space_1d"` = 一维周期线条/间距
  - `"contact_2d"` = 二维孔阵列
- **代码**：由 `build_mask_1d_line_space()` 和 `build_mask_2d_contact()` 处理
- **CD提取**：不同图案使用不同的CD提取算法

---

**`pitch_nm`** - 周期
- **含义**：一个重复单元的总长度（线宽+间距 or 孔间距）
- **典型值**：90 nm
- **计算关系**：特征尺寸 = pitch_nm × duty_cycle
- **工艺意义**：分辨率 ~ λ/NA，与 pitch 决定了工艺难度

---

**`duty_cycle`** - 占空比
- **含义**：特征部分占周期的比例 [0~1]
- **典型值**：0.5 （对称线宽/间距）
- **范围**：0.3～0.7 （极端值难以制造）
- **计算**：特征尺寸 = pitch_nm × duty_cycle

---

#### 光学参数

**`wavelength_nm`** - 曝光波长
- **常见值**：365 (i线) | 248 (KrF) | 193 (ArF) | 13.5 (EUV)
- **推荐**：193 nm （现代工艺标准）
- **分辨率关系**：分辨率 ~ λ/NA
- **权衡**：波长↓ → 分辨率↑，但景深↓（需更好的焦点控制）

---

**`na`** - 数值孔径
- **范围**：0.4～1.35 (immersion)
- **典型值**：0.85～0.93
- **代码**：在 `pupil_function()` 中定义相干极限频率 fc = NA/λ
- **效果**：高NA扩大工艺窗口，但景深↓

---

**`sigma_in` / `sigma_out`** - 环形光源的内/外半径
- **范围**：0～1 （标准化相对于瞳孔）
- **典型值**：sigma_in = 0.3，sigma_out = 0.7
- **配置**：定义部分相干照明在瞳孔平面的分布范围
- **采样**：在 `source_points_in_sigma_annulus()` 中随机采样光源点
- **效果对比**：
  - sigma_in=0, sigma_out=1.0 → 常规照明
  - sigma_in=0.3, sigma_out=0.7 → 环形照明（提高对比度）

---

**`n_source_samples`** - 光源采样点数
- **范围**：12～100
- **推荐**：12 (快速) | 41 (平衡) | 100+ (高精度)
- **原理**：蒙特卡洛采样光源点模拟部分相干性
- **权衡**：点数多 → 精度↑，但计算时间↑（平方关系）
- **最低要求**：≥12 为可信结果

---

#### 分辨率与网格参数

**`dx_nm`** - 空间采样间距
- **含义**：仿真网格的像素大小（纳米）
- **推荐值**：2 nm
- **范围**：1～5 nm
- **采样定理**：Nyquist定理要求 dx < λ/4，实际建议 dx < λ/10
- **权衡**：dx↓ → 精度↑，但内存/时间↑（平方关系）

---

**`sim_pitches`** - 仿真范围
- **含义**：模拟包含多少个周期
- **总宽度**：sim_pitches × pitch_nm
- **推荐值**：3～5
- **作用**：减少周期性边界效应
- **权衡**：值越大 → 计算越慢

---

#### 胶膜与工艺参数

**`peb_blur_nm`** - 曝后烘烤热扩散模糊
- **含义**：化学放大胶中的酸扩散程度（高斯模糊标准差σ）
- **范围**：5～50 nm
- **代码**：在 `develop()` 中用 `gaussian_blur_fft()` 实现
- **物理**：PEB是化学放大光刻的关键步骤，热扩散距离 ∝ √(D·t)
- **效果**：peb_blur↑ → CD↑（线条变粗、孔变大）

---

**`develop_threshold`** - 显影阈值
- **范围**：0～1 （归一化光强度）
- **典型值**：0.5
- **模型**（正性胶）：光强 > threshold → 显影掉（resist=0）
- **效果**：阈值↑ → CD 可能↓（需更强光才能显影）
- **工业应用**：不同胶体系的 contrast curve 决定此值
---

### 剂量和焦点扫描

```json
"dose_list": [0.9, 0.95, 1.0, 1.05, 1.1],
"defocus_list_nm": [-100, -50, 0, 50, 100]
```

#### 剂量扫描 (Dose Sweep)

**物理含义**：相对于标准剂量的光照强度扫描，模拟曝光量变化

**工艺窗口**：形成过程窗口图的**横轴**

**剂量影响**：
- dose < 1.0 → 欠量曝光，光强不足，CD 偏小
- dose = 1.0 → 标准剂量，目标 CD
- dose > 1.0 → 过量曝光，光强过多，CD 偏大

**应用**：代表工厂可容忍的曝光变化范围

**代码实现**：在 `photolithography_baseline.py` 中通过 `dose_rel` 参数控制光强度缩放

---

#### 焦点扫描 (Defocus Sweep)

**物理含义**：焦点距离晶圆的偏移量（纳米单位）

**工艺窗口**：形成过程窗口图的**纵轴**

**焦点影响**：
- defocus < 0 → 晶圆离焦点平面偏近，光学像质变差
- defocus = 0 → 焦点正确，光学像最优
- defocus > 0 → 晶圆离焦点平面偏远，光学像质变差

**景深(DOF)**：焦点容限 = 当CD仍在合格范围内时的焦点偏移范围
- 例如：±50nm 则 DOF ~ 100nm

**应用**：代表曝光台焦点控制的容限

**代码实现**：在 `pupil_function()` 中通过相位项 exp(...defocus_nm...) 实现

---

### RET 工艺优化

```json
"ret": {
  "psm": {
    "enabled": false,
    "phase_rad": 3.14,
    "region": "spaces"
  },
  "opc": {
    "enabled": false,
    "mask_bias_nm": 0.0
  }
}
```

#### PSM （相移掩膜）

**全称**：Phase Shift Mask

**功能**：
- 在掩膜特定区域刻蚀λ/2或π深沟槽
- 产生相移，增强相邻特征间的干涉消相

**参数**：
- `phase_rad` = 相移量（通常π = 3.14159）
- `region` = 相移区域
  - `"spaces"` = 间距相移
  - `"lines"` = 线条相移
  - `"background"` = 背景相移

**代码**：`psm.py` 中的 `apply_binary_psm_1d()` | `apply_binary_psm_2d()`

**效果**：
- 工艺窗口面积 ↑ 30～50%
- 显著提高良率和 CD 均一性

**工业应用**：现代工艺（≤32nm）的标准工具，特别是细孔阵列

---

#### OPC （光学邻近效应校正）

**全称**：Optical Proximity Correction

**功能**：
- 预先修改掩膜尺寸
- 补偿光学系统的邻近效应（小孔被邻近大特征阻挡）

**参数**：
- `mask_bias_nm` = 掩膜偏置量
  - 正值 → 特征膨胀（特征变大）
  - 负值 → 特征腐蚀（特征变小）

**代码实现**：
- 1D模式：`opc.py` 中 `apply_mask_bias_1d()` 调整 duty_cycle
- 2D模式：形态学膨胀/腐蚀

**工业意义**：消除图案间的相互影响，改善 CD 均一性

---

### 常见调整建议

| 目标 | 修改方向 |
|------|---------|
| CD 太小 | ↑ peb_blur_nm，↓ develop_threshold |
| CD 太大 | ↓ peb_blur_nm，↑ develop_threshold |
| 加快计算 | ↑ dx_nm，↓ n_source_samples，↓ sim_pitches |
| 扩大工艺窗口 | ↑ cd_tol_nm，启用 PSM/OPC |

---

## 2. litho_config_pipeline.json

POLY光刻步骤专用，结构同 `litho_config_scan.json`，通常参数较简单（如7nm工艺可能只做ideal掩膜或简单蚀刻）。

---

## 3. process_flow.json （7层工艺流程配置）

用于 `02_process_stages/run_7mask_pipeline.py` 完整工艺流程（从GDS导入到设备模型）。

### 主要配置段

---

#### GDS输入 (`gds_input`)

```json
{
  "enabled": true,
  "gds_path": "gds/basic.gds",
  "top_cell": "",
  "out_mask_dir": "masks",
  "grid_size": 1024
}
```

**`enabled`** - 是否启用GDS导入
- 若为 false，流程跳过GDS处理，直接用预存的 .npy 掩膜

---

**`gds_path`** - GDS文件位置
- 相对项目根目录的路径
- 代码：在 `ensure_masks()` 函数中读取
- 支持递归搜索多个 top_cell

---

**`top_cell`** - 顶单元名称
- 空字符串 `""` = 自动使用第一个 cell
- 明确指定 = 选择特定的设计单元
- 用于GDS有多个设计时

---

**`out_mask_dir`** - 掩膜输出目录
- 提取后的各层 .npy 文件会保存这里
- 被后续工艺阶段引用

---

**`grid_size`** - 光栅化分辨率
- 单位：像素
- 含义：将GDS的矢量图形栅格化为 grid_size × grid_size 的二值图
  - 1 = 图形
  - 0 = 背景
- 权衡：大值 = 高精度但内存 ↑

---

#### 工艺层定义 (`mask_layers`)

```json
"mask_layers": ["ACTIVE", "POLY", "NIMP", "PIMP", "CONT", "M1", "V1"]
```

**作用**：
- 定义工艺包含的所有层及其处理顺序
- 代码：`run_7mask_pipeline.py` 中遍历此列表
- 对每层应用相应的 `mask_strategy`

**顺序很重要**：
- POLY 通常首先处理（需光刻仿真）
- 后续层多为 ideal 或简化模型

---

#### 掩膜处理策略 (`mask_strategy`)

```json
"mask_strategy": {
  "POLY": {
    "litho_config": "configs/litho_config_pipeline.json"
  },
  "CONT": {
    "mode": "simple_litho",
    "bias_nm": 0.0,
    "overlay_nm": 10.0
  },
  "ACTIVE": {
    "mode": "ideal",
    "bias_nm": 0.0,
    "overlay_nm": 0.0
  }
}
```

**Mode 选项**

| mode | 说明 | 适用场景 |  处理方式 |
|------|------|--------|---------|
| `"ideal"` | 使用原始GDS掩膜，无优化 | 大特征/不关键层 | 直接读取GDS |
| `"simple_litho"` | 简化光刻模型（形态学CD调整） | 中等关键度层 | 膨胀/腐蚀 + 噪声 |
| `"full_litho"` | 完整光刻仿真 | 最关键层 | 调用完整光刻链 |

---

**`bias_nm`** - CD偏置

- **正值**：特征膨胀（特征变大）
- **负值**：特征腐蚀（特征变小）
- **实现**：形态学操作（cv2.dilate() / erode()）或改变 duty_cycle

---

**`overlay_nm`** - 叠对偏差

- **含义**：模拟相邻层之间的对齐误差
- **实现**：在掩膜图像上施加高斯随机变移
- **模拟**：实际工厂的层间对齐误差
- **典型值**：5～20 nm（工业值约 10nm）

---

#### 工艺阶段参数 (`stage_params`)

**基础网格**

```json
"dx_nm": 10
```

- **值**：仿真空间网格间距（纳米）
- **影响**：控制所有阶段的空间分辨率
- **权衡**：dx ↓ → 精度 ↑，但内存/时间 ↑（平方关系）
- **推荐**：通常 10～20 nm 为平衡

---

**Stage 2 蚀刻** (`etch`)

```json
"etch": {
  "pixel_um": 0.02,
  "base_rate_Apm": 5000.0,
  "film_thickness_A": 3000.0,
  "pressure_mTorr": 15.0,
  "rf_power_W": 400.0,
  "magnetic_field_mT": 50.0
}
```

**`pixel_um`** - 物理像素大小/特征分辨率（微米）
- 用于特征尺寸计算（micro_loading物理模型）

**`base_rate_Apm`** - 基础蚀刻速率（ Å/min ）
- 无任何负载时的参考值
- 实际速率 = base_rate × macro_loading × micro_loading × plasma_factor

**`film_thickness_A`** - 待蚀刻膜层厚度（ Ångström ）
- 定义过蚀量的计算
- 越厚 → 需要越高的非均匀性容限

**`pressure_mTorr`** - 腔体压强（毫托）
- 影响 `anisotropy_index()`
- 压力 ↓ → MFP ↑ → 各向异性 ↑（垂直蚀刻更优）

**`rf_power_W`** - 射频功率（瓦特）
- 影响离子能和离子通量
- 功率 ↑ → 蚀刻更快、各向异性更强

**`magnetic_field_mT`** - 磁场强度（毫特斯拉）
- 影响离子束的约束
- 磁场 ↑ → 离子通量 ↑ → 蚀刻更快

**代码背景**：`stage2_etch.py` 中 `effective_etch_rate_Apm()` 模拟了宏观加载（开口面积大 → 可用蚀刻剂减少）和微观加载（小特征蚀刻偏慢）。

---

**Stage 4 离子注入+退火** (`implant_thermal`)

```json
"implant_thermal": {
  "implant_dose_cm2": 1e13,
  "implant_energy_keV": 20.0,
  "tilt_deg": 7.0,
  "channeling": true,
  "screen_oxide_nm": 0.0,
  "anneal_mode": "RTA",
  "T_C": 1000.0,
  "t_s": 10.0
}
```

**`implant_dose_cm2`** - 注入剂量（cm⁻²）
- 决定掺杂浓度的积分值
- 代码：在 `gaussian_profile()` 中，C的积分 = dose

**`implant_energy_keV`** - 离子能量（千电子伏）
- 决定投影深度 Rp
- 代码：在 `rp_um()` 中，Rp ∝ (energy)^1.2
- 能量 ↑ → 深度 ↑

**`tilt_deg`** - 晶圆倾角（度）
- 缓解沟道效应（channeling tail）
- 工业标准值：7°

**`channeling`** - 是否启用沟道模型（布尔值）
- true → `add_channeling_tail()` 添加深层拖尾
- false → 纯高斯分布

**`screen_oxide_nm`** - 屏蔽氧化层（纳米）
- 减弱表面达到效应
- 典型值：0（无）或数十 nm

**`anneal_mode`** - 退火方式（字符串）
- `"RTA"` = 快速升温，时间短
- `"furnace"` = 炉式，扩散多
- 见 `anneal_sigma_um()` 函数

**`T_C`** - 退火温度（摄氏度）
- 决定扩散系数：D ∝ exp(-Ea/kT)
- 温度 ↑ → 扩散 ↑ → 结深 ↑

**`t_s`** - 退火时间（秒）
- 扩散距离：σ_diffusion ∝ √(D×t)
- 时间 ↑ → 扩散距离 ↑

**代码背景**：`stage4_thermal_implant.py` 实现了1D掺杂分布仿真。高斯分布 + 可选沟道拖尾 + 热扩散卷积，输出结点深度、峰值浓度等用于 Stage 6 器件模型。

---

**Stage 5 金属+CMP** (`met_cmp`)

```json
"met_cmp": {
  "overburden_nm": 300.0,
  "target_overburden_nm": 0.0,
  "pattern_density_window": 31
}
```

**`overburden_nm`** - 初始金属厚度（纳米）
- 相对于设计厚度的超厚量

**`target_overburden_nm`** - CMP后目标超过量（纳米）
- CMP平面化的目标值

**`pattern_density_window`** - CMP局部密度窗口大小（像素）
- 用于局部密度计算

**代码背景**：`stage5_metallization_cmp.py` 模拟了CMP对金属膜层的退火和平面化，过程窗口控制CMP速率非均匀性。

---

**Stage 6 器件** (`device`)

```json
"device": {
  "tox_nm": 2.0,
  "W_nm": 1000.0
}
```

**`tox_nm`** - 栅氧化层厚度（纳米）
- MOS器件的栅绝缘层

**`W_nm`** - 沟道宽度（纳米）
- MOS器件的有效沟道宽度

**代码背景**：`stage6_device.py` 使用前期的蚀刻/注入/金属结果计算MOS器件的 Vt 和漏电流。

---

## 2. litho_config_pipeline.json

POLY光刻步骤专用配置。

**特点**：
- 结构同 `litho_config_scan.json`
- 通常参数较简单
- 例如7nm工艺可能只做ideal掩膜或简化蚀刻

---

## 4. layer_map.json （GDS图层映射）

定义GDS中层号(layer number)和数据类型(data type)到工艺层的对应关系。

**格式**：`"工艺层名": [层号, 数据类型]`

---

### 示例映射

```json
{
  "ACTIVE": [2, 0],
  "POLY": [4, 0],
  "NIMP": [6, 0],
  "PIMP": [8, 0],
  "CONT": [10, 0],
  "M1": [12, 0],
  "V1": [99, 0]
}
```

**解释**：
- GDS中 layer=2, datatype=0 对应 ACTIVE 工艺层
- GDS中 layer=4, datatype=0 对应 POLY
- 以此类推...

---

### 工作流程

**步骤1：导出GDS**
- 从工艺库或PCell生成GDS文件
- 放到 `gds/` 目录

**步骤2：查看层号**
- 在 Klayout 或其他EDA工具中打开GDS
- 查看每个图层的 layer/datatype 信息

**步骤3：更新映射**
- 修改 `layer_map.json`
- 对应正确的层号

**步骤4：运行流程**
- 执行 `run_7mask_pipeline.py`
- 代码会自动：
  1. 从GDS中提取各层几何
  2. 根据 `layer_map.json` 的映射重命名为工艺层
  3. 按 `mask_strategy` 在 `process_flow.json` 中的设置做光刻仿真或ideal处理
  4. 输出为 `.npy` 掩膜并传递给后续工艺阶段

---

### 示例：修改POLY映射

如果使用OPC后的掩膜版本存放在GDS的层50：

```json
"POLY": [50, 0]
```

---

### 代码实现

在 `02_process_stages/run_7mask_pipeline.py` 的 `ensure_masks()` 函数中：

1. **读取GDS文件**
   - 使用 `gds_path` 和 `top_cell`

2. **按映射提取各层**
   - 根据 `layer_map.json` 的层号和数据类型

3. **光栅化处理**
   - 将矢量图形转为 grid_size × grid_size 的二值掩膜
   - 1 = 图形，0 = 背景

4. **保存掩膜**
   - 以 `.npy` 格式存储
   - 输出到 `out_mask_dir`

---

## 快速查找表

| 我想要... | 修改文件 | 调整参数 |
|----------|--------|--------|
| 单晶圆光刻仿真 | litho_config_scan.json | target_cd_nm, peb_blur_nm, dose/defocus |
| 7层工艺流程 | process_flow.json | mask_strategy, stage_params |
| 导入新GDS | layer_map.json | 对应GDS的层号 |
| 加快计算 | 任意config | dx_nm ↑, n_source_samples ↓ |
| 启用RET | litho_config_*.json | ret.psm/opc.enabled=true |

---

**最后修改**：2026-03-30

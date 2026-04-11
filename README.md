# 6202Project — Final Branch

此 `final` 分支为本次 Virtual Mini-Foundry 项目的最终提交版本，已对 `run-7` 管线与一对一流水线结果进行了对齐。GitHub 上可直接在该分支根目录查看本 `README.md`。

## 核心工作流

**`run.ipynb`** 是整个项目的执行驾驶舱，包含：
- **Stage1**：光刻模拟 (`01_lithography/run_project.py`)——生成光刻掩模的分析和光刻抗蚀剂轮廓
- **Stage2**：刻蚀 (`stage2_etch.py`)——基于光刻结果进行离子束刻蚀仿真
- **Stage3**：CVD (`stage3_cvd.py`)——高纵横比孔洞的化学气相沉积填充
- **Stage4**：注入与退火 (`stage4_thermal_implant.py`)——离子注入与温度处理
- **Stage5**：金属化与CMP (`stage5_metallization_cmp.py`)——铜互连与化学机械研磨
- **Stage6**：器件提取 (`stage6_device.py`)——计算最终的器件性能指标

运行 `run.ipynb` 即可执行完整的工艺流水线。

## 关键内容

- `01_lithography/`
  - 光刻与光刻仿真模块
  - 入口：`01_lithography/run_project.py`
- `02_process_stages/`
  - 后续工艺阶段连线：Stage2~Stage6
  - 核心流水线：`02_process_stages/run_7mask_pipeline.py`
- `configs/`
  - `litho_config_pipeline.json`：用于管线光刻的配置
  - `process_flow.json`：管线阶段参数与掩模策略
- `FINAL_REPORT_20260410.md`
  - 最终一致性报告与修复说明
- `outputs/Final_team_run/`
  - 最新最终运行结果输出目录

## 运行说明

在仓库根目录执行：

```bash
python 02_process_stages/run_7mask_pipeline.py --flow configs/process_flow.json --runname final
```

如果需要直接执行光刻阶段，可运行：

```bash
python 01_lithography/run_project.py --config configs/litho_config_pipeline.json
```

## 说明

本分支已同步 `run-7` 管线与逐阶段单独运行结果，并且已推送到远程 `origin/final`。
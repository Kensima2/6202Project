# 6202Project — Final Branch

此 `final` 分支为本次 Virtual Mini-Foundry 项目的最终提交版本，已对 `run-7` 管线与一对一流水线结果进行了对齐。GitHub 上可直接在该分支根目录查看本 `README.md`。

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
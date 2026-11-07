# 2026-11-07-04 去除辅助判断对照测试

六个指定固定PWM工况在三组RTL模型下均通过；额外ATC短低间隔测试两版同样失败。整体RTL门保持FAIL，未综合、布局布线、执行MAX-SDF或生成NoAux BIT，等待范围澄清。

- [详细结果](RESULTS.md)、[时序状态](TIMING_REPORT.md)、[机器状态](VALIDATION.json)。
- `rtl/`：完整参数化候选，默认ENABLE_AUX_CONFIRM=1，NoAux编译固定0；`reference/rtl/`：指定提交原版；`RTL.diff`：两个修改文件。
- `inputs/`：冻结激励、真实边沿、8参数、XCI/XDC及SHA256来源。
- `sim/`、`scripts/`：阈值/流水单元、三实例对照、分析和未执行的构建脚本。
- `results/REQUESTED_PWM_COMPARISON.csv`：六工况；`RTL_COMPARISON.csv`：完整含失败比较。
- `results/SHORT_GAPS.csv`、`CONFLICT_TRACE.csv`：不足2ns低间隔及首个混合极性帧。
- `results/rtl/`：全部原始CSV、错误、FIFO及日志，两次准备期失败单独保留。
- `SHA256SUMS.txt`、`FILE_LIST.csv`：校验和清单，均不包含自身以避免循环。

正式RTL、旧BIT及板上配置未在本轮改动。没有NoAux BIT，不用Corrected.bit冒充。

从原始CSV复核可调用 `scripts/analyze_rtl.py` 中的 `analyze(case,delay)`；运行参数由 `run_rtl.py` 保存。再次仿真应在独立副本使用新的输出目录，禁止覆盖原始记录。真实ASCII运行目录为 `codex_generate/.vivado_work/tdc_noaux_20261107_04`，没有创建虚拟盘符。功能FIFO模型只验证序列，不代表器件CDC/时序已通过。未重新拟合参数或剔除异常数据。

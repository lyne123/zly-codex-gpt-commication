# 复现步骤

使用 Vivado 2022.2、XSim、Python 3.13 和 Icarus Verilog。实验目录内的 Python 脚本从自身位置确定工程根目录；原运行的 ASCII 工作目录是 `codex_generate/.vivado_work/tdc_auxmatch_20261107_03`。没有新增盘符。所有运行目录有防覆盖检查，复核原结果不需要重新综合。

## 先核对证据

核对 `SHA256SUMS.txt`，读取 `VALIDATION.json`、`results/TIMING_ITERATIONS.csv`、`results/sdf/*/ANNOTATION.json` 和各次 `SUMMARY.json`。`inputs/SOURCE.json` 是任务开始时的冻结快照，零附加延迟和未修改标志描述的是开始状态，最终状态以 `VALIDATION.json` 为准。

`reference_F/rtl/` 是上一轮 F 的完整五个 RTL 文件，`production_original/rtl/` 是任务开始时实际生产版本。最终候选保存在 `variants/I_confirmation_pipe/`。`RTL.diff` 对比 F，`PRODUCTION_RTL.diff` 对比原生产版。

## RTL 和真实记录重放

在 PowerShell 中设置本任务目录变量 `$task`，然后运行：

```powershell
$env:TDC_VARIANT='I_confirmation_pipe'
python "$task/scripts/validate_rtl.py"
python "$task/scripts/check_backend.py"
```

已有结果目录不会被覆盖；复现时应在独立工作副本运行，并保留本次交付的原始结果。`prepare_I_validation.py`、`prepare_validation.py` 说明如何生成双实例检查平台。它们使用归档的完整 F 和 I，而不是重写一个近似辅助模型。真实 ILA CSV 第二行指定 UNSIGNED 进制；1024 个样本的实际移位寄存器与 claimed 状态由 RTL 推进。

三组 PWM 各 1344 个脉冲，分发模型每级延迟分别为 0/250/500 ps。500 MHz 比较器要求 I 的全部测量输出等于 F 前一拍，100 MHz 比较器按有效事件队列检查 FIFO 数据与错误顺序。输出到达时间没有改写进原始 CSV。额外后端测试只在 testbench 强制候选，覆盖重复上升、孤立下降、无效细码及粗计数回卷，不修改综合 RTL。

## 时序复核与物理复现

直接打开 `implementation/corrected_routed.dcp`，重新执行 `report_timing_summary` 和 `report_timing` 即可复核最终时序。`results/timing/implementation_fifo_reuse2/` 保存原报告及全部 14 条 ILA 负端点。不要用全局 WNS 代替核心 WNS。

实际运行顺序在 `results/TIMING_ITERATIONS.csv`；G/H/H2/H3 和定向物理优化均保留失败报告。`build_I.tcl` 记录最终逻辑的实际综合步骤及其当时增量参考；随后的 `restore_fifo_placement.tcl` 从该综合 DCP 继续，没有重复综合。最终恢复实际 AD23 生产版 FIFO 的 578 个匹配原语 BEL/LOC，另有 80 个 VCC/GND 常量不参与放置；没有修改 FIFO IP 配置。先成组设置 BEL，再设置 LOC。前端仅对明确的数据网做放置后复制，不重定时、不增加时序例外。

实际增量输入来自历史任务 `codex_generate/2026-11-07-01-上板边沿配对错误ILA定位/inputs/production_AD23.dcp`，SHA256 为 `9ff43fa9bd3cdb776fa7b30820b75d026a0d761da04ab83e83fed68db2846425`；可用 Git LFS 从已有历史取得，不在本次重复归档。位置源及校验值见 `inputs/FIFO_PLACEMENT_SOURCE.json`。中间失败 DCP 的原路径、大小和 SHA256 见 `results/LOCAL_INTERMEDIATE_FILES.json`。

从零重新综合时，使用完整最终 RTL、四个冻结 XCI、`inputs/compensation_params.tcl` 和 `inputs/combine_AD23.xdc`，保持 `build_I.tcl` 的综合选项。随后按最终物理脚本恢复位置并检查 STA。工具重新运行可能得到不同布局；本次可验证的 SDF/BIT 绑定对象是归档最终 DCP，不能把重跑结果自动当作同一证据。

## MAX-SDF 与统计复核

`sdf_pipeline.py` 的 `TDC_SDF_IMPL` 必须设置为 `implementation_fifo_reuse2`。它先核对核心门，再使用 XSim 的 simprims_ver/secureip、`--maxdelay --sdfmax` 和互连传输延迟。没有关闭 specify、timing check 或告警。

```powershell
$env:TDC_SDF_IMPL='implementation_fifo_reuse2'
python "$task/scripts/sdf_pipeline.py" prepare
python "$task/scripts/sdf_pipeline.py" compile
python "$task/scripts/sdf_pipeline.py" run --dataset minimal
python "$task/scripts/analyze_sdf.py" --dataset minimal
python "$task/scripts/sdf_pipeline.py" run --dataset full
python "$task/scripts/analyze_sdf.py" --dataset full
```

上述仿真指令用于新的运行副本，不覆盖已完成结果。原工作目录已有编译快照。归档最终 SDF 与网表位于 `implementation/`；复现时复制到新建的 ASCII XSim 目录，使用 `sim/tb_sdf.sv`、脚本生成的编译参数、原历史 XSim 库映射。Corrected 编译需要 `FRONTEND_PIPE1` 宏，仅改变 testbench 观测的粗计数信号，不改变被测网表。

Baseline 使用实际 AD23 生产 DCP 的只读导出，同样跑 `inputs/full.txt`；没有用旧 AF20 的统计报告代替本轮对照。对应执行加 `--variant baseline`。若仅复核统计，直接运行：

```powershell
python "$task/scripts/analyze_sdf.py" --dataset minimal
python "$task/scripts/analyze_sdf.py" --dataset full
python "$task/scripts/analyze_sdf.py" --variant baseline --dataset full
python "$task/scripts/compare_precision.py"
```

完整输入为原始 3512 脉冲，SHA256 冻结在 `inputs/SDF_INPUT_MANIFEST.json`。使用原事件 ID、冻结候选发射延迟及已声明的 2 ns 新增流水延迟关联，不重新拟合补偿或时间偏移。原始逐事件 CSV、错误 CSV、参考边沿、FIFO CSV 全部保留。统计同时列出各版全部有效样本及共同输入事件，禁止通过丢失异常样本制造精度改善。

`simulation.log.gz` 是完整原日志的无损压缩，原日志路径、原始 SHA256 及压缩文件 SHA256 位于 `RUN_MANIFEST.json`。MMCM 未连接 CLKOUT5/6、异步 TDL/辅助首级及启动复位首级告警的分类依据见 `results/sdf/WARNING_CLASSIFICATION.md`；其余告警仍阻断验收。工具给出严格全局 SDF 注释成功，构造项计数不是逐条注释成功率读回。

## BIT 与上板

只有 `export_accepted_bit.py` 的 RTL、核心 STA、最小和完整 MAX-SDF 门都通过，才允许从同一 DCP 导出 BIT/LTX。脚本不访问硬件。生产 BIT 与上一轮 Debug BIT 保留原位；A/B 操作和指标定义见 `HARDWARE_AB_TEST.md`。本任务不烧录 FPGA 或 Flash，也不声称完成了新版本上板实测。

# 复现说明

环境：Windows、Vivado 2022.2、xc7k325tffg900-2、Icarus Verilog 11.0 (devel, s20150603-642-g3bdb50da)、Python 3.13.0b1标准库。版本原始输出在logs。工具原路径分别为 `F:/Xilinx/Vivado/2022.2/bin`、`F:/iverilog/bin`、`F:/Program Files/Python313/python.exe`；其他安装位置需修改脚本中的工具路径并记录差异。

本次实际命令、日志、输入SHA、网表/SDF及失败结果均归档。原实验对应提交 `fa5fd072d015dbcd03a2f7d2c895dc93bd72fca1`，本轮未覆盖原工程实现结果。

## 先审查现有证据

1. `SHA256_MANIFEST.json`列出交付文件的字节数和SHA256；`ARCHIVE_MAPPING.csv`同时列出压缩前、压缩后SHA。大日志采用gzip无损压缩，解压后应与源SHA一致。
2. `results/*/*/*_validation/input_sha256.json`是实际运行时输入记录，其中U盘路径为本次运行时的映射路径；交付中的相对位置保持一致。所有主验证激励SHA必须为 `451a2cb59cc0704a9e5ac8454bb983237543705f2c4782789b3067be4d9fa76f`。
3. 每个完整仿真目录须有 `run_manifest.txt` 和正常结束标记 `TDC_SIM_DONE`。缺少结束标记的失败日志仍保留，但不纳入完整批次统计。
4. 查看 `results/ALL_CASE_METRICS.csv`、`RMS_COMPARISON.csv`、逐事件 `associated_timestamps.csv`、`measurements.csv`、`errors.csv` 和 `anomaly_pipeline_trace.csv`。全量不完整项目标记N/A，成功子集条件指标另列。

## 从冻结实现重跑

在本任务的独立副本中执行，不在原证据目录覆盖运行。复制 `rtl`、`original`、`inputs`、`sim`、`scripts`，以及四版本 `results/{original,optimized}/{baseline,compensated}` 的design.dcp/design.v/design.sdf和前端结构清单、`results/tdc_skew_calibration.csv`、`results/calibration_params.tcl`。不要复制已有的 `*_validation`、`*_calibration` 或build编译缓存。同一副本中的结果由脚本拒绝覆盖。

将空闲U盘映射到该副本；执行期间不要重映射U盘。原任务同时使用的T盘仅用于定位历史源文件，交付已包含四份实际网表/SDF/DCP和旧校准元数据，冻结实现重跑不再依赖T盘。

```powershell
subst U: 'D:\独立复现实验副本'
Push-Location U:\
try {
    & 'F:\Program Files\Python313\python.exe' U:/scripts/run_case.py original baseline rtl calibration
    & 'F:\Program Files\Python313\python.exe' U:/scripts/calibrate.py original baseline rtl
    & 'F:\Program Files\Python313\python.exe' U:/scripts/run_case.py original baseline rtl validation
} finally { Pop-Location }
```

按相同方式运行original/optimized、baseline/compensated、rtl/gate。RTL每版先运行calibration并调用calibrate.py建立独立事件关联延迟；该RTL拟合不作为物理补偿参数。优化gate每版也先运行自己的calibration，再calibrate.py分析；已有冻结8参数时不要加 `--promote`。original gate分析使用inputs/old_calibration.json。本轮原Baseline为O2/typical快照，后续编译为官方O3/debug off；原Compensated本轮全量7份CSV与上一轮O2完全一致。

gate编译使用真实静态$sdf_annotate、xelab --maxdelay、simprims_ver/secureip、slow/MAX、1 ps，以及transport/pulse参数；没有关闭timing checks。每个数据集有独立runtime目录。每次只编译一个gate版本，避免同时运行Vivado和xelab造成内存不足。完整主SDF运行时间约30分钟，所有原始告警写入日志。

完成后运行 `analyze_results.py --final`；对四版gate运行 `audit_sdf.py phase variant`，检查成功注释日志及编译网表/SDF SHA。最后 `report_results.py`仅接受8/8完整批次。未解压的gzip日志须先在副本中恢复为原文件名。

## 重新综合和实现

重新布局会改变TDL/输入路径的物理延迟，不能默认重建后的8参数仍适用。最终采用的物理分支及SHA见 `PHYSICAL_TRIALS.csv` 和最终实现的 `SOURCE_PROVENANCE.json`；完整分支脚本在scripts，首轮构建脚本为build_optimized.tcl，导出共用export_evidence.tcl。

新空工作副本中先复制 `inputs/validated_debug_hub_cache` 内容到 `build/shared_ip_cache`，再以原生短路径U作为PowerShell及Vivado的实际当前目录启动；仅将-source写为U盘而当前目录仍为中文路径，不足以避免本机嵌套IP工具故障。Debug Hub由厂商生成Tcl重放，相同参数与原/重放脚本SHA在inputs的PROVENANCE文件中。

先构建Baseline并冻结其实际DCP/SDF/网表，再运行独立800脉冲相位扫描并 `calibrate.py optimized baseline gate --promote` 生成新8参数。然后用这组冻结参数综合Compensated，使用自身实现的独立扫描检查fitted_matches_applied；若不一致，必须报告或开启新冻结迭代，不能混用SDF或使用验证集拟合。

Baseline物理分支的实际顺序为：`baseline_initial/design.dcp` → `baseline_power_checkpoint_flow.tcl` → `baseline_ila_cluster.tcl` → `baseline_ila_cluster_relaxed.tcl`。其中54 Slice试验为已保留的容量不足尝试，最终采用80 Slice结果。完整源综合入口为 `build_optimized.tcl baseline`；从归档的冻结baseline_initial DCP重做物理分支可避免重新综合依赖IP。各分支输出目录必须为空，已有证据仅在独立副本中改名保存，不覆盖原目录。

本机补偿版project模式的ILA综合曾发生EXCEPTION_ACCESS_VIOLATION。缓存匹配存在但未实际命中；首次单进程synth_ip在project上下文产生“不支持project模式”警告，实际生成了IP产品，全部日志和小型dump已保留。最终顶层改用正式非工程流程读取实际产品，未将缓存匹配误称为缓存命中。新空副本可直接使用以下受支持流程，不需要重现该失败过程：

```powershell
Push-Location U:\
try {
    & 'F:\Xilinx\Vivado\2022.2\bin\vivado.bat' -mode batch -source U:/scripts/build_optimized.tcl -tclargs compensated prepare_only
    & 'F:\Xilinx\Vivado\2022.2\bin\vivado.bat' -mode batch -source U:/scripts/build_compensated_nonproject.tcl
} finally { Pop-Location }
```

prepare_only只创建独立工程和IP源产品，第二步在非工程上下文调用synth_ip并独立综合顶层。实际应用参数由results/calibration_params.tcl冻结，所有顶层参数与对应BIT/DCP/SDF一起归档。不要用未完成的project run状态作为非工程实现是否完成的判据。

失败尝试不作为最终Timing PASS依据。500 MHz需同时检查WNS/TNS/WHS/THS、失败端点、最小周期/脉宽、约束覆盖和bus skew。板级IO预算、上板及其他PVT动态时序角尚未执行。证据保留缺口见EVIDENCE_LIMITATIONS.md。

# 复核与复现

先核对SHA256SUMS.txt与输入SOURCE.json。源码在rtl/，原提交完整五文件在reference/rtl/。硬件NoAux编译固定ENABLE_AUX_CONFIRM=0；默认1保留AuxOn。两版阈值、8参数、CARRY4和原确认级一致。

scripts/prepare.py及prepare_tb.py记录生成过程；已有冻结目录禁止原地重建。RTL运行命令在run_rtl.py，三个完整实例共享sys_clk/复位/同一原始3512波形；0/250/500ps LUT延迟仅是功能模型应力，不代表新器件标定。重新仿真使用独立工作副本与新的结果目录，不覆盖已交付原始CSV。scripts/analyze_rtl.py的analyze(case,delay)可直接复核统计。

用户范围记录在SCOPE_DECISION.md、SCOPED_RTL_GATE.json。高低间隔资格只读取full_truth.csv，不读测量结果。原RTL_GATE.json的FAIL及SHA绑定不变。全部3512波形仍参与SDF，3504为范围内资格，不是修改后的激励。

本次仅一次综合/布局布线，脚本为prepare_build.py及build_noaux.tcl。原始增量参考为任务03的implementation/corrected_routed.dcp，SHA01004b1502ef357304503269eaba73c9e41415456b58ecac76c393a53a6d9584；FIFO位置参考及来源已冻结，578个原语恢复BEL/LOC。四个XCI相同，共用Vivado 2022.2既有IP缓存。独立ASCII运行目录为codex_generate/.vivado_work/tdc_noaux_20261107_04；没有虚拟盘符。

打开implementation/NoAux_routed.dcp并重新report_timing即可复核实际STA；不要用旧Corrected时序代替。重跑布局可能非逐字节确定，本次SDF/BIT以归档路由DCP与其SHA绑定为准。

MAX-SDF命令由scripts/sdf_pipeline.py提供：prepare、compile、run --dataset minimal及run --dataset full。使用XSim simprims_ver/secureip及slow/MAX SDF，FRONTEND_PIPE1仅选择testbench观察的粗计数影子。input_extra_cycles=1相对旧关联基准；NoAux相对Corrected新增延迟为0。

在已交付CSV上复核无需重跑仿真：

```powershell
python scripts/analyze_sdf.py --dataset minimal
python scripts/analyze_scoped_sdf.py --dataset minimal
python scripts/analyze_sdf.py --dataset full
python scripts/analyze_scoped_sdf.py --dataset full
python scripts/compare_sdf.py
```

完整SUMMARY保留原完整结果，SCOPED_SUMMARY是用户约定范围的新结果。初次因103及Merge码2尚未归属而产生的保守范围FAIL另存before_error_attribution文件，实际事件与未修改Merge重放证据见SDF_ERROR_ATTRIBUTION.md。后续分析只补充事件归属，不改原始CSV/SDF/日志或原完整FAIL。

AuxOn对照使用指定提交03任务的corrected/full完整SDF数据，来源和每个重要文件SHA在AUX_ON_SDF_REFERENCE.json；需历史Git LFS文件时从该不可变提交取得，不重复打包旧大文件。SDF_COMPARISON.csv同时展示全部关联输出与共同3504事件，正确子集不冒充整体。

simulation.log.gz是完整原日志的无损压缩；RUN_MANIFEST记录原始日志位置、原始SHA及压缩SHA。告警分类依据见SDF_WARNING_CLASSIFICATION.md。参数不重新拟合，统计不剔除离群值。

export_noaux_bit.py严格检查范围RTL、核心STA、最小及完整范围SDF和DCP校验后，才从同一DCP导出NoAux.bit/ltx。它不连接硬件。本轮没有烧录FPGA/Flash，旧Corrected BIT不覆盖。

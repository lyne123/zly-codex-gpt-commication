# 复现实验

## 工具与入口

- 实体任务目录：`D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/codex_generate/2026-11-04-02-四相TDC固定延迟补偿验证`。
- Vivado 2022.2：`F:/Xilinx/Vivado/2022.2/bin/vivado.bat`，xc7k325tffg900-2。
- Icarus Verilog 11.0：`F:/iverilog/bin/iverilog.exe`与同目录`vvp.exe`。
- 数据分析：Python标准库，本次使用Python 3.13。
- 绘图：复用只读Python 3.12.14环境 `D:/00-code/FPGA_Prj/fpga_tdc_v3/codex_generate/.venv-rms-stable/Scripts/python.exe`；Matplotlib 3.9.2、NumPy 2.1.3，版本另见`requirements-plot.txt`。

Windows Vivado子进程在中文路径出现flex scanner/TclStackFree错误，因此实际构建使用`subst T:`指向本任务目录。T盘仅是路径映射，所有实体产物仍在中文日期任务目录。另有ASCII junction `codex_generate/tdc_skew_20261104_02`供查看文件；Vivado必须使用T盘，避免其规范化junction后再次进入中文路径。

```powershell
Set-Location 'D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/codex_generate/2026-11-04-02-四相TDC固定延迟补偿验证'
subst
# 仅在T盘空闲时建立；若已有映射，先核对确实指向本任务。
subst T: 'D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/codex_generate/2026-11-04-02-四相TDC固定延迟补偿验证'
$env:TDC_TASK_ROOT='T:/'
$env:PYTHONUTF8='1'
```

## 从头运行

交付目录保存执行证据，构建和仿真脚本会拒绝覆盖已有DCP或测量CSV。从头运行时，先在`codex_generate`下新建符合`YYYY-MM-DD-NN-中文任务名称`的任务目录，复制本任务的`baseline/`、`inputs/`、`rtl/`、`scripts/`、`sim/`及`requirements-plot.txt`，建立空的`build/`、`results/`、`logs/`。不要复制已运行的build/results，不要删除本交付中的证据。

确认所有使用旧T盘映射的Vivado/XSim进程均已结束后，核对映射并解除旧T盘，再映射新任务目录。`run.ps1`会检查映射归属，不会覆盖其他任务的T盘。然后在新任务实体目录执行：

```powershell
.\scripts\run.ps1 -Stage all
```

可通过`-Vivado`、`-Iverilog`、`-Vvp`、`-Python`、`-PlotPython`指定不同安装位置。需要其他Python绘图环境时，按`requirements-plot.txt`安装到自选环境，不修改所复用的历史环境。

完整流程为：生成确定性输入→脚本自检→RTL旁路完整回归→独立补偿单元测试→原始baseline实现与位流→SDF冒烟→独立800脉冲校准→冻结8参数→独立补偿版实现与位流→两套SDF验证→事件ID关联→RMSE/Bias/STD与数字重算→图表和报告。遇到工具或数据完整性错误会停止，不会把未执行项标为PASS。静态或动态时序失败则如实进入报告，不以关闭检查绕过。

## 分阶段命令

```powershell
.\scripts\run.ps1 -Stage generate
.\scripts\run.ps1 -Stage test-scripts
.\scripts\run.ps1 -Stage rtl
.\scripts\run.ps1 -Stage test-compensation
.\scripts\run.ps1 -Stage build-baseline
.\scripts\run.ps1 -Stage gate-smoke
.\scripts\run.ps1 -Stage gate-calibration
.\scripts\run.ps1 -Stage calibrate
.\scripts\run.ps1 -Stage build-compensated
.\scripts\run.ps1 -Stage gate-baseline-validation
.\scripts\run.ps1 -Stage gate-compensated-validation
.\scripts\run.ps1 -Stage fifo-probes
.\scripts\run.ps1 -Stage analyze
```

`run_gate.ps1 -Prepare`仅为对应实现编译一次真实网表与SDF；后续独立批次复用同一编译快照，每批重新启动仿真。没有波形窗口与全层级波形记录，完整CSV和所有warning仍写入文件，所有timing checks保留。`run_sim.tcl`另保留Vivado直接launch_simulation入口，本次最初SDF冒烟使用该方式。

本次主批次先记录了结果FIFO的100MHz序列和两个overflow标志，错误FIFO的100MHz读出由追加的独立`fifo_probe`仿真集补证；没有为旧主CSV补写虚构列。两版诊断均真实重现8输入、7脉宽和一个错误2，500MHz入队与100MHz读出一致。新版测试平台以后在主批次也记录`error_fifo.csv`。短诊断不替代主验证，主帧测试仍为FAIL。

若只复跑冻结SDF，可复制整个任务到新目录并映射其T盘，只将**新副本**的对应`gate_validation`目录改名备份，然后运行`run_gate.ps1 -Variant baseline -Dataset validation -Prepare`和补偿版同命令；这样使用冻结DCP，不重新布局布线。错误片段诊断依赖当前物理布局相位；换布局后若未重现预期故障，脚本会拒绝宣称诊断覆盖，不应强制内部错误信号或调整主验证输入来制造通过。

## 证据、协议和回退

- `baseline/rtl/`是修改前五文件的恢复快照；`baseline/sha256.json`记录原始哈希。本目录没有Git仓库，未创建或合并main分支。
- 正式补偿RTL在本任务`rtl/`，活动工程只更新`tdc_meas_top.v`、`tdc_time_locate.v`。恢复时先确认活动文件没有后续用户修改，再从baseline复制这两个文件；其余三文件未改。
- 原始baseline位流由原RTL快照生成，物理上没有补偿；新增RTL的`ENABLE_SKEW_COMP=0`显式旁路已逐拍证明与原模块一致。补偿版明确设置`ENABLE_SKEW_COMP=1`并载入`calibration_params.tcl`，不能用零占位参数冒充已校准版本。
- XPR/XDC/XCI只读复制自相邻Kintex-7工程。新基线的物理XDC仅在实现阶段LATE加载，参考XPR却也在综合阶段加载；这项构建差异已记录，不宣称旧位流逐位复刻。两版本使用相同设置；500 MHz没有降低，没有新增false/multicycle例外。
- 校准输入文件保持已执行v1调度，其真值的边沿/脉宽未改；验证使用修正调度。旧版输入与真值保存在`inputs/stimulus_v1/`，每个正式SDF批次还保存独立输入和真值副本及哈希，避免后续生成器改动破坏关联。
- ATC协议尚无完整依据。`sim/atc_assumptions.json`仅是临时配置：bank/channel升序、帧头5%后95%、每单元一个载波周期、10 kHz正弦与峰值起始的对称三角载波自然比较。它不代表已验证的实际芯片协议。
- 修改`TAP_PS`、RTL、XDC、IP或物理布局后，必须重新执行独立校准并冻结新参数，再运行验证；不能用旧CSV证明新布局。
- 位流仅用于后续受控上板验证，当前签核状态以`TIMING_REPORT.md`及`FINAL_RMS_COMPARISON.md`为准。SDF器件模型结果不等同于硅片精度。

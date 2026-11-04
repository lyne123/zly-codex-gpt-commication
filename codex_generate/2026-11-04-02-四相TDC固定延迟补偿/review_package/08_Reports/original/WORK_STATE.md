# 执行状态

## 最终状态（以下覆盖后文早期进度）

主实验、两位流及两版错误FIFO独立SDF诊断均已执行结束。活动RTL只修改top和locate，已与任务rtl副本一致。18位signed八参数、Stage2选择+Stage3减偏移、显式generate旁路保持原5级；CW2/CW10各5044单元检查及完整RTL回归通过。校准800脉冲从baseline真实DCP/SDF获取，8项按0/90/180/270升/降均34698/34710/34861/34796ps，文件和参数已冻结。

两版真实SDF主验证均3512输入/3509输出/3507正确配对；missingR=[2918,2984,3050]，missingF=[2917,2983]，两错配，5条业务错误，无重复/FIFO overflow/X。原候选在同帧混合R/F时丢帧，根因与临时协议的边沿对齐帧头+中心对齐SPWM造成1.293～1.736ns低电平相关，真实raw掩码11/11/9已记录。保持刺激不变，失败组主表N/A，成功子集统计另列。

25.3ns RMSE135.6023599→53.1471542ps；20MHz50%143.2689778→69.7353569ps；10MHz完整暂定帧125.4056→66.7000ps、1056/1056。重新实现输出与同baseline样本数字重算在3507个正确配对上逐点相同。前端1842同名网1606路由相同/236变化，输入到末tap四路径延迟两版相同。STA baseline WNS-.163/TNS-.589/12setup；comp WNS-.173/TNS-1.083/19setup；hold+.058，无签核。大量MMCM未使用CLKOUT5/6零周期及异步采样timing告警完整保留。

两个bit均在results/baseline/tdc_baseline.bit、results/compensated/tdc_compensated.bit，DCP/网表/SDF/报告已在同目录。七类PNG/SVG/PDF已生成且全部视觉检查；主帧图展示错配x与缺失空圈，条件统计图明确frame incomplete。错误FIFO主批未最初采集100MHz码，追加独立simset fifo_probe（不影响主仿真缓存）从原输入3047..3054平移235160000ps，8输入7宽度+错误2，两个版本写入/100MHz读出[2]一致，两个fifo_check.json=PASS。整体实验仍FAIL。

生成报告脚本report.py、证据核对verify_delivery.py已完成；最后需运行report.py生成最新哈希清单，再verify_delivery.py核对，终端打印完整结论并回复用户。T盘映射保留以打开Vivado工程。不要再执行全量SDF或改参数/输入；所有运行已完成。原始sdf初次smoke、cal、主验证及probe各有独立输入副本/哈希。校准保留v1实际50.00～52.02ns调度，验证已在执行前修复相位重复额外2ns问题，旧刺激在inputs/stimulus_v1。8值未使用验证集回调。

## 早期进度（仅作历史）

本任务从当前工程五份原始RTL开始，原始快照与SHA256已保存。五文件与相邻Kintex-7工程逐字节相同，依赖只读复制。未改其他工程。

- 原始完整RTL理想模型回归：3512输入、3512脉宽、7024时间戳、业务错误0、FIFO序列相等；证据 `results/baseline/rtl_validation/functional_check.json`。不是物理精度数据。
- 激励及统计自检通过：`logs/test_experiment.log`。800校准脉冲，3512验证脉冲，验证含两帧各1056单元。
- 初始Vivado脚本create_ip_run集合参数错误已修复，首次错误日志保留。
- 中文路径工具子进程出现flex scanner/TclStackFree错误。现用 `subst T:` 指向本任务真实目录，环境变量 `TDC_TASK_ROOT=T:/`，Vivado工程位于 `build/baseline_ascii/tdc_baseline.xpr`。
- 当前成功重试的Vivado日志 `logs/baseline_console3.log`、session 26614。四个IP和顶层综合完成，正在实现阶段。不要同时改写此工程。
- 辅助ASCII junction `codex_generate/tdc_skew_20261104_02` 指向本任务目录，无额外产物副本。Vivado必须使用T盘以避免规范化junction后重新出现中文路径。
- `scripts/build.tcl`、`scripts/run_sim.tcl`、`sim/tb_tdc.sv`、`scripts/experiment.py`已建立；gate监测的层级信号名需在实际导出的网表中核对。
- 尚未得到实现后校准数据，不能给出物理补偿参数。尚未修改活动RTL。`sim/tb_compensation.sv`是待补偿RTL完成后执行的独立算术/旁路测试。
- 需要继续：完成baseline实现导出→gate smoke→800相位校准→核对raw/candidate/timestamp公式→生成8参数→补偿RTL及旁路单元测试→完整gate baseline/compensated验证和独立compensated实现→图表、哈希清单、报告与bit归档。
- 发现历史setup违例、未设PWM/复位input delay、注释管脚/TDL位置过时、debug hub频率声明不符。详细在 `RTL_REVIEW.md`。
- 新基线仅实现阶段加载原物理XDC，而参考XPR还在综合阶段加载；差异已在审查报告中明确。未加入false path、未放宽500MHz。
- ATC实际协议缺失：`sim/atc_assumptions.json`集中记录临时假设，不能宣称真实ATC协议验证。
- 旧2026-11-03固定补偿任务是Lattice器件，禁止借用其参数、数据或结果。

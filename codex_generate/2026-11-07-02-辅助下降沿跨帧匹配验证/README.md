# 2026-11-07-02 辅助下降沿跨帧匹配验证

**结论：真实错误已逐拍复现；确认0°候选被前帧辅助匹配范围阻断。可靠正式修复未完成，保留Baseline，不生成新BIT。**

来源：调试结果Commit `2e9cf594aed51c67d48c090fdea9b92125f7822b`；正式RTL来源 `ba978229094a8621b30770177727d8e70b831a74`。目标XC7K325T-FFG900-2，Vivado2022.2。归档分支`codex/2026-11-07-02-aux-fall-slot-alignment`，不合并main。

## 实际结果

1. 原RTL边界重放与真实CSV的13,209项核对一致。辅助fall_now在730，0°下降包在731，相差一个500MHz周期（2ns）；此时事件已在previous[3]且未claimed，原0°只接受now，导致final_type0=00。后端配对错误是结果。
2. 比较A/B/C/D/E/F。B恢复该例但改变18次原选择；C新增正常下降丢失；D保守局部恢复但传播压力下仍不完整。E/F在三组功能模型下各1344脉冲全部正确，恢复真实丢失下降且不改变原有效帧，但实际核心时序失败：E -0.729ns，F -0.579ns。
3. **最终采用A，正式5个RTL逐字节保持不变。** 所有候选位于variants/，不作为生产版本。8个补偿参数、TDL、粗/细测计算、FIFO、候选选择模块和配对状态机均未修改。
4. SDF与实现后网表已经导出用于审查；核心时序门失败，未进行SDF注释/仿真。未生成或复制Baseline.bit，未生成Corrected.bit，未烧录。原生产与Debug BIT均保持原SHA256，位置见inputs/EXTERNAL_REFERENCES.json。
5. 原设计会在一帧确认多个相位候选，再择一输出。真实记录A/E/F均有21个这样的帧。本轮验证最终重复输出为0，不声称confirm层严格onehot；这一字面验收项未实现，也未改动选择算法来追求它。

## 查阅顺序

- REAL_CSV_REPRODUCTION.md：位序、观测延迟、731第一次可见丢失及尚缺证据。
- SCHEME_COMPARISON.md：所有方案、错误计数、归属约束、功能测试定义。
- TIMING_BEFORE_AFTER.md：两次失败实现及实际核心路径。
- results/VALIDATION.json：最终机器可读状态；results/SCHEME_STATISTICS.csv：18组完整RTL比较。
- inputs/TRIGGER_A.csv：原始上板CSV；results/replay/：六方案边界重放；results/pwm/：全链路功能CSV、日志、参考事件配对。
- original/rtl/：完整原正式RTL；variants/：完整独立候选；RTL.diff：未采用F相对Baseline；FORMAL_RTL.diff为空，表示正式无变化。
- results/implementation{,_F}/：失败候选路由DCP、slow/MAX SDF、网表、约束与时序报告；logs/：完整失败日志。文件名corrected_routed及Corrected.ltx来自导出脚本，只是候选命名，**不是验收通过的Corrected版本**。

## 复现

需要Python3.13（标准库）、Icarus Verilog及Vivado2022.2。脚本默认Icarus位于F:/iverilog/bin、Vivado位于F:/Xilinx/Vivado/2022.2/bin；迁移电脑时仅调整工具位置，不调整激励或参数。所有工作目录使用真实ASCII路径，禁止创建虚拟盘符。

1. 校验SHA256SUMS.txt；检查inputs/SOURCE.json。已保存的结果不要覆盖；在独立工程副本中复现。
2. 运行scripts/materialize_runtime.py，从冻结副本建立codex_generate/.vivado_work/tdc_auxfall_20261107_02。
3. 运行scripts/analyze_capture.py解析真实CSV；运行scripts/replay.py重放A/B/C/D。通过环境变量TDC_COMPARE_VARIANTS=E_guarded或F_factored分别运行其重放。
4. 同样设置TDC_COMPARE_VARIANTS后运行scripts/test_pwm.py；它会拒绝覆盖已有运行CSV。scripts/check_guard.py默认E，设置TDC_GUARD_VARIANT=F_factored检查F。scripts/check_equivalence.py检查E/F的19个输出CSV完全一致。
5. inputs/ip/保留原4个XCI；inputs/combine_AD23.xdc与compensation_params.tcl保持原样。scripts/build_candidate.tcl及build_factored.tcl保存实际实现流程，注册IP/OOC缓存和AD23参考DCP使用inputs/EXTERNAL_REFERENCES.json的旧原件。缓存只是加速，未列为实验数据。运行前按原脚本把这些输入复制到同名ASCII运行目录；分别执行Vivado batch。这两次实现预期以CORE_TIMING_FAIL结束，不应绕过门限生成BIT。
6. scripts/run_sdf.py与sim/tb_sdf.sv仅是已准备但未执行的后续方案；它会检查核心门限，当前失败实现不允许启动。无SDF PASS或注释成功率可报告。

## 尚缺证据与最小后续方向

数字确认门控机制已确认；尚缺270°编码前thermo/raw_edge_type/ready和实际输入模拟波形，不能认定270°type00的具体物理原因，不能证明新增流水线统一错一拍，也不能排除所有毛刺。建议下一步只在现有辅助history流水中预计算所需事件资格，减少500MHz末级全局归约及晚到pack270扇出，并先做等价/时序评估；本任务未实施该结构调整。可靠修复还须通过核心时序、SDF及真实上板回归后才能采用。

本任务没有修改任何真实实验数据，没有重校准，没有覆盖原生产或Debug文件。SHA256清单覆盖全部归档输入、代码、CSV、日志和报告；未上传的旧原件有明确路径、大小与哈希，不是遗漏本次证据。

# NoAux 上板实测：10 MHz / 50%

日期：2026-11-07，北京时间。**NoAux 下载及采集成功；零配对错误验收 FAIL。** 本次没有修改 RTL、参数、约束或实验激励，没有重新综合或布局布线，没有写入 Flash。

## 固件与条件

- 本次固件源提交：`05b35fc946a0dd87c28ff6a1695bd4f8de34252a`，同一任务独立分支 `codex/2026-11-07-04-tdc-no-aux`。
- `implementation/NoAux.bit`，SHA256：`967f33ac042342b99c2c9fe9c03250c97b3ca8fad1ea1b03a4f0cf55dd609604`。`ENABLE_AUX_CONFIRM=0`，链间补偿仍然开启；NoAux 不等于关闭链间补偿。
- 匹配的 LTX：`implementation/NoAux.ltx`，SHA256：`dcf8e20b6389ec92e7f90afb3bd878865c86cfb940755f67d223603cbac0b2c8`。
- C3067D03ABCD 目标、XC7K325T，AD23 输入。沿用用户最近确认的 10 MHz / 50%，本轮未读取仪器设置；信号源由用户操作。
- 本次用户授权“现在上板实测一下”。原 `BIT_MANIFEST.json`、`VALIDATION.json` 和 `inputs/SOURCE.json` 中未烧录/未授权字段保留原离线交付时点的快照，本报告及 `results/hardware_04/` 记录后续授权和实际下载。
- 下载后 EOS=1、DONE=1、CRC_ERROR=0、IDCODE_ERROR=0，两个 ILA UUID 与 LTX 一致。以实际下载日志和固件 SHA 绑定版本，不能只凭相同 ILA UUID 区分 NoAux 与 Corrected。
- u_ila3 使用 100 MHz，观测 FIFO 输出的脉宽、valid、独立错误流及 PWM 输入。u_ila2 的 500 MHz 内部波形本次未采集。

## 本次结果

| 指标 | 结果 |
| --- | ---: |
| 原始 ILA 窗口 / 总采样点 | 50 / 102400 |
| 有效输出全部保留 | 10011 |
| 主统计有效输出 / 额外保留 | 10000 / 11 |
| 重复上升沿，错误码 1 | 202 |
| 孤立下降沿，错误码 2 | 29 |
| 时间越界，错误码 3 | 0 |
| 未知错误码 / 未知错误有效位 | 0 / 0 |
| valid=1 但数值未知或越界 | 0 |
| 平均脉宽 | 50.3843125 ns |
| 样本标准差 STD | 76.055889 ps |
| 平均绝对偏差 MAE，相对 50 ns 设定值 | 384.312500 ps |
| 最大绝对偏差，相对 50 ns 设定值 | 779 ps |
| RMSE，相对 50 ns 设定值 | 391.765258 ps |
| 最小 / 最大脉宽 | 50.015 / 50.779 ns |

没有 MSO54 实测参考值，`reference_width_ps=null`。上述绝对偏差是**相对于信号源 50 ns 设定值**，不能称为经过校准的绝对测量误差。MAE 按每次测量取绝对值再平均，不以有正负抵消的 Bias 代替。

100 MHz 的 PWM 粗采样得到中位周期 100 ns，高电平采样比例 50.1924%，与此前声明的 10 MHz / 50% 条件相符。相邻上升沿间隔中，10 个采样周期有 10166 次，9 个有 8 次，11 个有 7 次。该采样分辨率不能鉴别亚周期毛刺、精确脉宽或模拟输入质量，不能据此认定存在或不存在毛刺。

## 统计和错误含义

- 按窗口采集顺序及窗内采样序号，取前 10000 个 valid=1 且数值可读、处于输出模范围的测量。没有离群值筛选；全部原始、无效和额外记录保留。
- STD 使用 `sqrt(sum((T-mean(T))^2)/(N-1))`，N=10000，不除以 sqrt(2)。MAE 使用 `mean(abs(T-50000 ps))`；MaxAbs 使用 `max(abs(T-50000 ps))`。
- 计入截止第 10000 个有效输出时的全部独立错误事件。本次全部 231 条错误均在截止位置前，额外 11 个有效输出没有额外错误。
- 错误码直接对应保留的 `tdc_time_merge.v`：1 为 `timestamp_valid && in_range && timestamp_edge_type && rise_pending`；2 为 `timestamp_valid && in_range && !timestamp_edge_type && !rise_pending`；3 为 `timestamp_valid && !in_range`。
- 错误流通过独立 FIFO 到 100 MHz，不携带原始事件时间或与脉宽一一对应的标签；当前 ILA3 也不观测两个 FIFO 的 overflow 状态。不能把 10000 个有效输出声称为 10000 个输入全部正确配对，不能推导全局有效测量率。
- 各 ILA 窗口之间有 JTAG 上传间隔，间隔内的事件未采集。本表错误数限于保存的采样窗口，不是连续整段运行的累计计数器。

## 与历史 Corrected 实测的参照

| 指标 | 历史 Corrected，辅助确认 ON | 本次 NoAux |
| --- | ---: | ---: |
| 主统计有效输出 | 10000 | 10000 |
| 重复上升沿 | 152 | 202 |
| 孤立下降沿 | 37 | 29 |
| 时间越界 | 0 | 0 |
| 样本标准差，ps | 72.609953 | 76.055889 |
| MAE 相对 50 ns 设定值，ps | 405.579800 | 384.312500 |
| MaxAbs 相对 50 ns 设定值，ps | 805 | 779 |

历史数据来自不可变提交 `94d69bf159db3cd2269616f44e17a23eb2b9d467` 的任务 03，同为此前声明的 10 MHz / 50%。引用路径和 SHA 见 `results/hardware_validation_10MHz_50/HISTORICAL_REFERENCE.json`，数值表见 `COMPARISON.csv`。这是不同时间的两次采样，**不是本轮连续切换固件的严格 A/B 实验**；仪器实际波形、温度和布线延迟差异未被控制，不能用该表量化辅助确认的因果效果。

本次能够确认：辅助确认已旁路的 NoAux 版本仍然有重复上升沿和孤立下降沿，未达到零错误。当前数据没有观测到错误对应的完整前端链路，尚不能区分 TDL 漏沿/多报、候选筛选、输入毛刺或其他原因，也不能据此认定配对状态机有缺陷。需要错误前后的 500 MHz 候选、极性、timestamp 及配对状态才可进一步定位。本轮不修改测量算法或阈值。

## 原始证据及复现

- `results/hardware_01/`：第一次真实下载报 `End of startup status: LOW`，没有有效采集。
- `results/hardware_status_01/`、`hardware_02/`、`hardware_03/`：随后目标不可用的原始失败日志、USB 枚举及已核实为 Codex 启动的调试服务恢复记录。未删除或改写失败日志。
- 用户释放并重插 JTAG 后仍不可用，随后确认板卡断电重启；清理原 Codex 服务后，`hardware_04/preflight.log` 成功识别器件，下载前 DONE=0。
- `results/hardware_04/`：成功下载的原始日志、配置寄存器、实际执行 Tcl 和 50 份 `ACTIVITY_*.csv`。CSV 与原生导出逐字节核对一致。
- `results/hardware_validation_10MHz_50/`：`SAMPLES.csv`、`ERROR_EVENTS.csv`、`INVALID_RECORDS.csv`、`CAPTURES.csv`、`SUMMARY.json`，各样本保留源窗口及采样下标。
- 仅使用归档文件重新统计：在任务目录运行 `python scripts/analyze_hardware.py --attempt hardware_04 --archived`，不依赖本机原生运行目录，不执行烧录；使用原生目录时省略 `--archived`。Tcl 和 Python 的总有效计数均为 10011。
- 再次硬件采集时，为新尝试建立独立空目录，把 BIT/LTX 的实际绝对路径、`capture_dir`、`program_requested=1`、`max_windows=100`、`target_valid=10000` 写入新的 `config.tcl`，检查 C306 目标可用后运行 `vivado -mode batch -source program_noaux.tcl -tclargs config.tcl`。必须沿用 `scripts/program_noaux.tcl` 并核对固件 SHA；不要指向已有采集目录。该操作会重新配置 FPGA，不写 Flash。
- 正式 RTL、候选 RTL、补偿输入文件均与原 SHA 清单一致。旧生产 BIT、Corrected BIT 和旧 Debug BIT 保留。本次结束已关闭 JTAG Target，板上保留 NoAux 易失配置。

# 最终实验报告

**整体验收：FAIL。**

Timing（500 MHz同步STA）：FAIL；Functional：FAIL；Compensation：PASS。

本次基于上一轮完整本地工程和Commit fa5fd072d015dbcd03a2f7d2c895dc93bd72fca1，经版本核对后独立构建，没有覆盖旧BIT/DCP或原数据。

## 修改与时序根因

仅fine_layer与locate两份RTL修改。实际原始违例包括跨相位范围判定、补偿串联减法、ILA内部和错误FIFO写指针/full路径，详见TIMING_ROOT_CAUSE.md及100条路径CSV。前端增加1拍并整体对齐，补偿常量折叠，结合PerfOptimized_high/Explore/post-route AggressiveExplore；没有降频或新增时序例外。

完整时序和资源对照见[TIMING_BEFORE_AFTER.md](TIMING_BEFORE_AFTER.md)，连续测量及因果边界见[CONTINUOUS_PWM_VALIDATION.md](CONTINUOUS_PWM_VALIDATION.md)。

## 新参数（ps）

| 相位 | Rise | Fall |
|---|---:|---:|
| 0° | 36081 | 36081 |
| 90° | 36011 | 36011 |
| 180° | 35742 | 35742 |
| 270° | 35756 | 35756 |

这些绝对值包含公共流水线与输入分发延迟；结构新增公共延迟2 ns。OLD_VS_NEW_CALIBRATION.csv同时给出相对0°通道差、R/F独立统计、最终补偿实现自己的拟合值及一致性。硬件参数只来自独立post-route校准，验证数据未参与拟合。

## 精度与文件

全部RMSE/Bias/STD/MaxAbs和样本数量在RMS_COMPARISON.csv及逐事件CSV。RMSE=sqrt(mean(error²))，Bias=mean(error)，STD为总体去均值标准差；漏沿/错配时全量N/A，条件统计明确区分。
10 MHz完整暂定帧与10 MHz/50%是两个不同项目；原135.602→53.147、143.269→69.735、125.406→66.700 ps的证据保留在原始对照。

- 新Baseline BIT：results/optimized/baseline/Baseline_Optimized.bit
- 新Compensated BIT：results/optimized/compensated/Compensated_Optimized.bit
- 对应DCP、SDF、网表及Setup/Hold在各版本同目录。
- 原始CSV、正常/失败日志、真实边沿、编译TB快照和SHA均保留。

## 限制与下一步

500 MHz已收敛与否以实际表格为准，不能用RMSE改善代替时序或功能通过。若混合极性丢帧仍在，后续单独审查帧边界、辅助同步窗口及多事件处理能力，本轮没有引入多事件队列。
MMCM未用输出模型警告、异步TDL模型与硅片亚稳态差异、真实ATC协议、板级IO延迟和PVT仍需独立确认。
首轮并行IP内存不足、Debug Hub嵌套库加载及中文工作目录TclStackFree等工具失败均保留，采用串行、独立官方生成脚本和U盘原生工作目录恢复。
Git以独立分支codex/2026-11-05-01-tdc-timing-optimization归档；每个版本由本目录所属Git提交及文件SHA追溯，实际推送Commit ID在执行反馈给出。

## 证据保留边界

首轮Vivado原生run目录的部分中间报告/检查点随reset_run被工具清理；该轮61份最终导出证据已冻结并记录SHA，原始旧实验及主仿真CSV均保持。详见[EVIDENCE_LIMITATIONS.md](EVIDENCE_LIMITATIONS.md)。后续从独立DCP分支继续，不用重生成文件冒充已遗失的原文件。

补偿实现自身相位扫描与实际应用8参数逐项一致：**True**。不一致时Compensation必须FAIL，不能把Baseline拟合值称为补偿实现自身拟合值。

按事件ID连接的八组全量对照见results/EVENT_COMPARISON.csv；原异常及新异常重点审查表见results/ANOMALY_EVENT_REVIEW.csv，完整逐周期接口轨迹仍保留在各批次目录。

实际补偿顶层采用独立非工程综合；增量RuntimeOptimized自动覆盖了请求的place/phys/route策略。SOURCE_PROVENANCE.json和原始日志给出实际生效策略。冷打开DCP并完整更新时序后的fresh_*报告与正式导出指标一致，未用瞬态优化估计代替最终结果。

追加发现ILA2原始生成OOC约束为10 ns（100 MHz），集成约束仍为2 ns（500 MHz）。这是需优先核查的IP综合目标差异，不是本轮已证明的唯一根因。本轮未执行2 ns OOC映射对照；下一轮应独立建立正确IP综合目标并验证合法性/映射，再处理locate Stage5回卷与选择路径，重新做物理校准和完整SDF。原XDC证据在inputs/ILA_OOC_TIMING_EVIDENCE，未修改厂商生成文件。

## 实测结果摘要

| 版本 | WNS ns | TNS ns | WHS ns | THS ns | Setup失败数 |
|---|---:|---:|---:|---:|---:|
| baseline | -0.050 | -0.166 | 0.054 | 0.000 | 14 |
| compensated | -0.050 | -0.185 | 0.054 | 0.000 | 15 |

新两版均正确配对3506/3512（99.8292%），丢Rise 3、Fall 3，错配3。与原版3R/2F/2错配相比，多丢Fall事件3049并增加1次错配；没有重复事件或FIFO溢出。

新版本polarity_conflict、repeat、merge错误均为0，仍不能通过功能验收。理想候选RTL重放新raw精确得到7018个输出且0冲突；旧版3次混合极性冲突的机制不能直接套用到新漏沿。前端有效样本缺失/失真与辅助确认门控需要进一步内部观察，详见CONTINUOUS_PWM_VALIDATION.md。

| 测试 | 原Base RMSE ps | 原Comp RMSE ps | 新Base RMSE ps | 新Comp RMSE ps | 样本数 |
|---|---:|---:|---:|---:|---:|
| 25.3 ns | 135.602 | 53.147 | 219.659 | 74.357 | 200 |
| 20 MHz / 50% | 143.269 | 69.735 | 244.622 | 79.079 | 200 |
| 10 MHz暂定帧 | 125.406 | 66.700 | 153.279 | 69.417 | 1056 |
| 10 MHz / 50% | 0.000 | 0.000 | 0.000 | 0.000 | 200 |

新补偿相对新Base能减少固定延迟偏差，但相对原Comp的上述三个非零RMSE均有退化。完整帧丢沿/错配项目的全量RMSE标N/A；成功子集指标仅作条件统计，不替代完整验收。

# 验收结果：PASS（数字仿真与核心时序）

基于 `0d741ec0cba376da4dc83a7069e1dfb2b28edce7` 的 F 功能规则，采用 I 专用确认流水级及实际生产 FIFO 物理位置复用。真实 ILA 样本 731 的下降沿恢复；262144 组组合保护检查、三组各 1344 脉冲完整 RTL 对照及后端错误/回卷检查通过。没有改变 8 个补偿参数、TDL 编码、相位优先级、候选/配对规则或 FIFO 数据格式。

## 功能与延迟

F 的原确认优先、整帧为空才回退、纯极性、唯一未 claimed 的 previous 事件和防重复归属规则保留。与 F 在已声明的固定一拍延迟后输出数值逐位一致，**不是同拍等价**。500 MHz 全测量束、时间戳、脉宽与错误晚 2 ns；Locate 本体仍五级，通过粗计数影子保持原事件的数值。100 MHz FIFO 检查数量/顺序/数据/错误码一致，不承诺固定到达时差。修改三个 RTL：fine_layer、time_locate、meas_top；Candidate、Merge、约束输入及四个 IP 配置不变。

## MAX-SDF

XSim 2022.2、slow/MAX、simprims_ver/secureip，严格全局 SDF 注释成功，未出现未匹配诊断，时序检查全部开启。112 脉冲最小测试和原始 3512 脉冲完整测试均通过：完整输入上升/下降各 3512，正确配对 3512/3512，FIFO 输出 3512，漏沿、重复、错配、业务错误及 FIFO 错误均为零。

原生产 AD23 同激励对照正确配对 3512/3512；其功能门状态为 `True`，原始结果保留。它是生产版对照，不是时序不通过的原 F 实现。F→I 数值不变来自 RTL 双实例检查；生产版→I 的物理精度变化来自本轮相同激励 SDF，不能混为一个比较。

未连接 MMCM 输出、异步首级采样及启动复位首级告警单独保留分类。最初未分类告警导致的 FAIL 摘要仍在归档；核对实际 RTL、网表和发生时间后仅对明确类别分类。详见 `results/sdf/WARNING_CLASSIFICATION.md`。没有关闭检查来获得 PASS。

## 时序

核心 Setup 最差 +0.099 ns，Hold 最差 +0.054 ns，核心 TNS/THS 为零。全局 WNS/TNS 为 -0.050/-0.166 ns，保留 14 个历史 ILA2 非反馈负端点；详见 `TIMING_BEFORE_AFTER.md`。此前组合版本和物理优化的实际失败证据全部保留。

## 精度对照

| 样本群 | 版本 | N | Bias ps | RMSE ps | STD ps（样本） | MaxAbs ps |
|---|---|---:|---:|---:|---:|---:|
| all_valid | baseline | 3512 | -0.474 | 65.210 | 65.218 | 189 |
| all_valid | corrected | 3512 | -0.474 | 65.210 | 65.218 | 189 |
| same_input_common_ID | baseline | 3512 | -0.474 | 65.210 | 65.218 | 189 |
| same_input_common_ID | corrected | 3512 | -0.474 | 65.210 | 65.218 | 189 |

共同输入事件数 3512。完整各测试组见 `results/PRECISION_COMPARISON.csv`。Bias=平均脉宽误差；RMSE=sqrt(mean(error²))；STD 使用 N−1 分母；没有除以 sqrt(2)，没有剔除异常或重新拟合参数。不同脉宽混合汇总只作为误差分布统计，不能当作单一固定脉宽的重复性。

## 交付与限制

已从通过 SDF 的同一最终路由 DCP 生成 `implementation/Corrected.bit` 和匹配 `Corrected.ltx`。两份旧 BIT 保留原位并重新校验 SHA256，未覆盖。正式工程只采用上述三处经过验收的 RTL 修改。没有烧录 FPGA/Flash，没有新版本真实上板采集；本结果不代表已排除真实输入毛刺或所有模拟采样问题。下一步按 `HARDWARE_AB_TEST.md` 做相同输入条件的 A/B。

归档分支 `codex/2026-11-07-03-aux-match-timing-fix`，提交消息 `2026-11-07-03-辅助跨帧匹配时序优化`；推送结果和实际 Commit SHA 在执行结束时单独报告。不得从本文件推断推送已经成功。

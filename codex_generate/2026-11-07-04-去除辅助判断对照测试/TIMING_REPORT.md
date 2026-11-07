# NoAux实现与核心时序

本次实际NoAux路由DCP的核心Setup/Hold均通过；没有用Corrected报告代替。

| 模块 | Setup最差ns | Hold最差ns |
|---|---:|---:|
| u_tdc_fine_layer | +0.138 | +0.108 |
| u_tdc_time_candicate | +0.265 | +0.119 |
| u_tdc_time_locate | +0.293 | +0.110 |
| u_tdc_time_merge | +0.166 | +0.134 |
| u_fifo_tdc_result | +0.099 | +0.095 |
| u_fifo_tdc_error | +0.128 | +0.054 |

核心最差Setup +0.099ns、Hold +0.054ns，负端点均0。全局WNS/TNS为-0.050/-0.166ns，WHS/THS为+0.054/0.000ns。保留14个历史ILA2非反馈Setup负端点，全部原始起终点见results/timing/negative_max.csv；不把全局负裕量改成PASS。

使用Vivado 2022.2、XC7K325T-FFG900-2，原500MHz四相/100MHz时钟、AD23输入及XDC不变。FIFO恢复578个已有原语BEL/LOC作为物理复用，80个VCC/GND常量不放置；FIFO逻辑和IP配置不改。四个XCI在生成和综合后与冻结配置逐字节一致。没有新增false path、multicycle或时钟例外，没有增加流水线或降低频率。

严格MAX SDF注释已成功，112脉冲最小测试（含2ns高低边界）通过；完整3512激励已执行完成。最小测试没有未分类核心时序告警。BIT交付状态以VALIDATION及各SDF摘要为准。本轮未连接或烧录FPGA。

## 最终SDF状态

最小范围门=True；完整范围门=True；原完整SDF门=False。实际记录与校验均已归档，未烧录。

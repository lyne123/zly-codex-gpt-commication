# 核心时序验收：FAIL，停止采用

Vivado2022.2，XC7K325T-FFG900-2，500MHz；参考是实际AD23生产实现，不是历史AF20 SDF实现。每个候选独立实现一次；F针对E已定位的晚到控制负路径作等价分解，并非反复调整实现种子。

| 实现 | 全局WNS ns | 全局TNS ns | WHS ns | THS ns | 核心最差Setup ns | 核心负端点 |
|---|---:|---:|---:|---:|---:|---:|
| 冻结AD23 Baseline | -0.050 | -0.166 | +0.054 | 0 | +0.050 | 0 |
| E 全局保护回退 | -0.729 | -6.418 | +0.054 | 0 | -0.729 | 12 |
| F 等价余因子 | -0.579 | -5.560 | +0.054 | 0 | -0.579 | 14 |

Baseline的14个历史负端点都在ILA2。E新增12个核心端点，核心TNS=-6.252ns；F新增14个核心端点，核心TNS=-5.394ns。它们不能按历史ILA违例忽略。所有版本Hold负端点为0。

E最差：pack270_to90_reg[9]（90°）→3级LUT6→sync_edge_polarity_reg[3]（0°），要求1.5ns，数据路径1.771ns，其中布线1.419ns。F将晚到类型控制限于末级选择，但最差转移到g_align[2].rise_q_reg[1]→3级LUT6+末级LUT5→sync_edge_valid_reg[3]，要求2ns，数据路径2.528ns，布线2.069ns；另外pack270→claimed两个端点分别-0.123/-0.081ns。

没有新增false path、关闭时序检查、修改频率、改补偿参数或增加测量流水级。没有为ILA历史违例做优化。保持正式Baseline，不再进行无依据的第三次实现。

完整报告、核心模块最差路径和负端点CSV见results/implementation及results/implementation_F。两次实现导出的slow/MAX SDF、网表与最终路由DCP用于审查失败实现；SDF尚未注释或执行仿真，不能说后仿通过。综合/布线原始日志保存在logs/。

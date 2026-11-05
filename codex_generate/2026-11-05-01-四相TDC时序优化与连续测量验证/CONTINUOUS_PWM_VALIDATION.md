# 连续PWM测量验证

主激励SHA256：`451a2cb59cc0704a9e5ac8454bb983237543705f2c4782789b3067be4d9fa76f`。所有组使用同一文件、事件编号、真实边沿时间；没有重随机生成或改变异常处输入。RTL模型为理想原语功能模型，SDF为真实路由后slow/MAX。

| 阶段 | 版本 | 模型 | 正确配对/3512 | 丢R | 丢F | 重复R/F | 错配 | 结果/错误FIFO序列 |
|---|---|---|---:|---:|---:|---|---:|---|
| original | baseline | rtl | 3512/3512 | 0 | 0 | 0/0 | 0 | True/True |
| original | baseline | gate | 3507/3512 | 3 | 2 | 0/0 | 2 | True/True |
| original | compensated | rtl | 3512/3512 | 0 | 0 | 0/0 | 0 | True/True |
| original | compensated | gate | 3507/3512 | 3 | 2 | 0/0 | 2 | True/True |
| optimized | baseline | rtl | 3512/3512 | 0 | 0 | 0/0 | 0 | True/True |
| optimized | baseline | gate | 3506/3512 | 3 | 3 | 0/0 | 3 | True/True |
| optimized | compensated | rtl | 3512/3512 | 0 | 0 | 0/0 | 0 | True/True |
| optimized | compensated | gate | 3506/3512 | 3 | 3 | 0/0 | 3 | True/True |

每个测试项目的预期/实际升降沿、重复边沿、配对/错配、RMSE/Bias/STD/MaxAbs和有效率见[ALL_CASE_METRICS.csv](results/ALL_CASE_METRICS.csv)。错配归属按下降沿参考ID记录；所有异常输出仍保存在measurements.csv，不用行号强行对齐。
完整性失败时全量指标N/A，成功子集conditional指标单列；没有删除异常后宣称整体通过。ATC帧仍是16×(64+2)=1056的暂定协议，不等同真实芯片协议验收。

## 因果对照

原Baseline本轮SDF全量7份关键CSV与上一轮逐字节一致。独立raw→候选器重放7019个输出及3个冲突时间完全一致，见candidate_replay_verification.json；混合极性整帧丢弃是确定性规则，暂未改为多事件队列。
尚未建立两个版本都无同步Setup违例的最终对照，不能排除同步时序影响。raw重放只证明给定四相帧时的算法响应，不单独证明物理成因。
- original/baseline：丢R `[2918, 2984, 3050]`，丢F `[2917, 2983]`；事件级错误及逐周期接口轨迹在该批次目录。
- original/compensated：丢R `[2918, 2984, 3050]`，丢F `[2917, 2983]`；事件级错误及逐周期接口轨迹在该批次目录。
- optimized/baseline：丢R `[2918, 2984, 3050]`，丢F `[2917, 2983, 3049]`；事件级错误及逐周期接口轨迹在该批次目录。
- optimized/compensated：丢R `[2918, 2984, 3050]`，丢F `[2917, 2983, 3049]`；事件级错误及逐周期接口轨迹在该批次目录。

原五个错误脉冲ID为[2917, 2918, 2983, 2984, 3050]；其中在新两版仍未得到唯一正确脉宽的ID为[2917, 2918, 2983, 2984, 3050]。不能用旧ID修复掩盖其他位置的新异常。
冷打开两份最终DCP并update_timing -full的fresh_*报告已核对原导出结果。Base剩余14条Setup均在ILA2，失败寄存器扇出不返回TDC/FIFO；Comp另有locate回卷/选择到timestamp的−0.019 ns路径，向后可到13个merge端点。详见negative_setup_reachability.csv和module_worst_setup.csv。ILA隔离证据不能替代剩余测量路径STA签核。
SDF为标称时钟的确定性slow/MAX仿真，STA还包含clock uncertainty等预算；没有动态同步setuphold告警不能据此宣布STA通过。

候选冲突/repeat标志由TB独立记录，原工程没有把它们全部接入错误FIFO；错误FIFO只核对实际merge错误入队序列。TDL异步setup/hold、同步数字逻辑、复位和MMCM未用输出的模型告警分别统计，不全局豁免。

## 新版本的直接机制与旧版不同

新两版errors.csv均无polarity_conflict、repeat或merge错误，但仍有3R/3F缺失和3错配。三份前端原始数据raw.csv、candidate.csv、sampled_taps.csv在新Base/Comp之间逐字节一致。未修改的理想候选RTL重放新raw，7018个输出的时间、极性、索引和码值全部精确重现，冲突数量为0，见optimized_candidate_replay_verification.json。因此不能把新漏沿直接套用旧版的3次混合极性冲突解释。
MISSING_RAW_EDGE_REVIEW.csv进一步检查真值后12–32 ns的原始有效通道（独立校准观察延迟约21–23 ns）：三个缺失Rise窗口内没有有效Rise通道；三个缺失Fall窗口内的有效Fall信息更吻合后一帧头下降沿，距离前一真实Fall仍有3.7–4.3 ns误差，远超校准残差131 ps范围。该表仅用于定位，不筛除或修改RMS样本。
现有证据把新异常定位到候选输入的有效样本形成/保留之前；还不能在TDL编码、异步辅助检测及confirm_edge门控之间确定唯一成因。Base测量数字路径STA为正且剩余ILA失败不回馈测量通路，进一步说明不能只用同步Setup违例解释这些新漏沿。Comp仍有−0.019 ns测量路径预算违例，整体验收继续FAIL。下一轮需要增加前端内部观察，未在本轮改候选规则或引入多事件队列。

# 最终验收：STOP_NO_ACCEPTED_FIX

真实上板错误复现：PASS，13,209项实际RTL核对。数字丢失机制确认：辅助事件730、TDL0包731，跨一拍；0°不接受previous[3]，confirm过滤。样本728实际是fall_slots=1000而非fall_previous。

候选E/F的功能输出测试：PASS，每方案3×1344脉冲，所有上升/下降配对、重复、孤立、错配、FIFO与宽度容差检查通过。原记录下降timestamp从19恢复20，重复上升从1降至0；这是重放结果，不是修复后上板实测。原多相确认帧仍存在，不声称严格onehot通过。

核心实现：FAIL，E新增12个负端点，最差-0.729ns；F新增14个负端点，最差-0.579ns。不能以ILA历史例外放行。SDF文件已生成，注释及后仿未执行。没有生成Baseline.bit或Corrected.bit。

最终保持A/Baseline，正式RTL五文件哈希不变，原生产与Debug BIT哈希不变；没有烧录。根本物理相位偏移来源仍不充分，270°编码前信号与模拟输入证据尚缺。详见README、真实CSV复现、方案比较和时序报告。

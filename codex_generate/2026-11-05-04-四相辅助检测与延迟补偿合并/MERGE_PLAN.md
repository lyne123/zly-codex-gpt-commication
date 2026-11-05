# 合并方案及来源

原Compensated：d30dfeb9779f7d3c4859fbfb300bebd2d9481a7b，上一轮任务results/optimized/compensated。
已验证四相辅助Baseline：6b341d88497541f23eaefee1cfad4e4925c7f2aa。

正式工程及历史版本均不覆盖。新独立实现的5个RTL与四相辅助Baseline逐字节一致。
相对于原Compensated，仅tdc_fine_layer.v发生辅助检测变更；top/locate/candidate/merge逐字节一致。
合并通过综合generic及RTL测试平台参数启用原有补偿，不重新实现补偿代码。

补偿在候选选择之后、Time Locate第2/3级计算。原有18位有符号参数、19位中细运算、21位时间戳、扩展符号运算及模2048000ps回卷保持不变；单位ps，10ps/tap，没有新增舍入。
sel_index 0/1/2/3对应90°/180°/270°/下一周期0°，不能直接当物理TDL序号。
8参数由旧独立SDF校准冻结，包含公共流水线；rise/fall分别选择，虽然本次冻结数值相等。
新RTL的辅助流水线、采样顺序、去重/归属和confirm_edge均不修改。

修改/新增文件清单：本任务rtl副本(相对于原Compensated仅fine_layer变化)、inputs/compensation_params.tcl、sim/compensation_parameters.vh、验证/构建/报告脚本；codex_generate/README.md新增索引。
先RTL全3512及补偿边界检查，再综合实现和完整MAX-SDF；任一失败停止后续依赖步骤，BIT另设验收门槛。

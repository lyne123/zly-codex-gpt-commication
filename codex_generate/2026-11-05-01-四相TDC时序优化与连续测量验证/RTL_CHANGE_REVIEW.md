# RTL修改审查

本次正式源码与归档副本仅修改两份Verilog：

- `tdc_fine_layer.v`：四个编码器在本相位寄存code/type/ready，将范围判定从1.5 ns跨相位路径移到2 ns同相位路径；aux门控INDEX从5到6，窗口宽度保持两拍。
- `tdc_time_locate.v`：8个mid−offset在展开时计算，Stage2选择并寄存，Stage3只减fine；保持18位signed参数、19位relative、模回卷、显式旁路和原5级valid/type。

PWM分发7个LUT1、64个CARRY4、256个采样FF、tap数/意义、采样极性、粗计数机制、候选选择/混合极性规则、merge配对和错误标志均保留。候选器、merge、顶层未修改。原版本在original/{baseline,compensated}/rtl，后版本在rtl，差异在RTL_CHANGES.patch。

自动化验证：完整冻结激励134238周期/7270有效四相帧逐拍等价原版延后一拍；CW=2/10各5044次补偿测试，覆盖8映射、signed极值、复位、连续valid、零参数、旁路和多次回卷。硬件新增延迟只有前端1拍；绝对偏移重新校准，未沿用旧参数冒充新实现。

## 物理实现分支

BRAM优化在重布局前执行，将工具确认不需要READ_FIRST的ILA trace端改为NO_CHANGE，修复最小周期违规；路由后执行会被跳过的失败尝试亦保留。依据实际ILA计数/复位路径的布线瓶颈尝试驱动复制与局部布局；54 Slice试验容量不足，扩展为80 Slice后再验证。没有对TDL添加新Pblock或改变其LOC。完整实际试验及参数见PHYSICAL_TRIALS.csv、SOURCE_PROVENANCE.json和执行日志。
测试平台按网表真实粗计数总线名选择观察点宏；这是只读观察适配，不修改网表或测量算法。首次名称不匹配的失败展开日志保留。

AUX_GATE_INDEX旁的旧bit4说明为遗留注释，旧实现实际常量为5，新实现为6；以代码及完整激励逐拍对齐断言为准。冻结后未再修改RTL注释或源码，相关SHA保持一致。

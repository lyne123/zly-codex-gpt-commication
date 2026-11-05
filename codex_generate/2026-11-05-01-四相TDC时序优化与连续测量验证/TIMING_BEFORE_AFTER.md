# 时序与资源前后对照

500 MHz保持不变；没有新增false path/multicycle，也没有关闭任何timing check。重要内部端点时钟约束完整；PWM和复位2个外部异步输入仍缺板级input delay，板级IO签核另列为未执行。

| 指标 | 原Baseline | 优化Baseline | 原Compensated | 优化Compensated |
|---|---:|---:|---:|---:|
| wns_ns | -0.163 | -0.050 | -0.173 | -0.050 |
| tns_ns | -0.589 | -0.166 | -1.083 | -0.185 |
| whs_ns | 0.058 | 0.054 | 0.058 | 0.054 |
| ths_ns | 0.000 | 0.000 | 0.000 | 0.000 |
| wpws_ns | 0.161 | 0.161 | 0.161 | 0.161 |
| tpws_ns | 0.000 | 0.000 | 0.000 | 0.000 |
| setup_failing | 12.000 | 14.000 | 19.000 | 15.000 |
| hold_failing | 0.000 | 0.000 | 0.000 | 0.000 |
| pulse_width_failing | 0.000 | 0.000 | 0.000 | 0.000 |
| setup_endpoints | 8402.000 | 8480.000 | 8483.000 | 8525.000 |
| hold_endpoints | 8346.000 | 8424.000 | 8427.000 | 8469.000 |
| bus_skew_min_slack_ns | 1.438 | 1.456 | 1.438 | 1.230 |

## 实际资源

| 资源 | 原Baseline | 优化Baseline | 原Compensated | 优化Compensated |
|---|---:|---:|---:|---:|
| Slice LUTs | 2995 | 3015 | 3019 | 3033 |
| Slice Registers | 4920 | 4970 | 4944 | 4984 |
| Block RAM Tile | 5 | 5 | 5 | 5 |
| CARRY4 | 190 | 190 | 195 | 192 |

优化包含RTL及映射/物理策略变化，资源差异不能全部归因于新增寄存级。编码器code/type/ready与辅助门控共同+1周期（2 ns）；候选器5级、locate5级、merge和FIFO逻辑规则保持。

500 MHz同步STA：**FAIL**。各版本完整Setup/Hold、check_timing、时钟交互、例外、CDC和路由报告在results/original_inspection与results/optimized。

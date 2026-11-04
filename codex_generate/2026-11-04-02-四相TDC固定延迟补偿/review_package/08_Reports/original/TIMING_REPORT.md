# 静态与动态时序报告

| 版本 | WNS ns | TNS ns | Setup失败端点 | WHS ns | Hold失败端点 | WPWS ns |
|---|---:|---:|---:|---:|---:|---:|
| baseline | -0.163 | -0.589 | 12 | 0.058 | 0 | 0.161 |
| compensated | -0.173 | -1.083 | 19 | 0.058 | 0 | 0.161 |

两个版本都没有降低500 MHz或放宽时序例外。Baseline最差路径为90°计1编码到0°pack90_d1极性位，另有500 MHz ILA路径；不能靠数字偏移解决。原PWM和复位没有板级input delay，debug hub频率参数与实际100 MHz不符，详见RTL_REVIEW。

## SDF与动态告警

SDF采用实际路由后网表、slow/MAX、1ps时间分辨率。每批保留elaboration.log、实际注释输入哈希、simulation.log和原始CSV。64个TDL CARRY4、256个采样FF、7个LUT1均在SDF关键清单中；未把清单覆盖冒充工具逐路径百分比。

| 版本 | 分类 | 检查 | 告警次数 |
|---|---|---|---:|
| baseline | MMCM_unused_CLKOUT5_6 | $period | 1073744 |
| baseline | PWM_async_synchronizer | $setuphold | 383 |
| baseline | TDL_async_sampling | $setuphold | 85549 |
| baseline | other_logic_or_IP | $recrem | 2 |
| baseline | other_logic_or_IP | $setuphold | 109 |
| compensated | MMCM_unused_CLKOUT5_6 | $period | 1073744 |
| compensated | PWM_async_synchronizer | $setuphold | 383 |
| compensated | TDL_async_sampling | $setuphold | 85549 |
| compensated | other_logic_or_IP | $recrem | 2 |
| compensated | other_logic_or_IP | $setuphold | 109 |

全部告警原文保留，没有notimingchecks/no_notifier/suppress、没有编辑厂商模型。MMCM未使用CLKOUT5/6的$period检查值显示0，原因尚未获厂商确认，不能擅自归类为可忽略误报。TDL与pwm_meta的异步采样setup/hold告警也保留；模型出现数值输出不等于硬件不存在亚稳态。

ASYNCHRONOUS寄存器属性来自原始RTL；仿真器对其使用的XON配置属于原工程/厂商模型行为，本次没有人为禁用通知器。有效输出X/Z及FIFO异常由独立监测CSV检查。

整体时序验收：FAIL。STA分析min/max角；动态实验只执行slow/MAX，未将其他角或上板测试标为通过。

# 独立物理校准报告

固定校准文件为sim/stimuli/calibration.txt及对应真实边沿CSV，800脉冲；主验证3512脉冲完全独立，未参与拟合。上升沿、下降沿各自拟合四条通道。RTL扫描仅用于建立事件关联，不作为物理补偿参数。

对raw.csv中mask有效的通道记录：`Traw = ((Craw+6) mod 1024)*2000 + mid[index] - fine`，按2048000 ps取模；mid按sel_index0/1/2/3为500/1000/1500/2000 ps，对应90/180/270/下一周期0°。Rise的fine=code*10 ps，Fall的fine=(64-code)*10 ps。
每个raw帧使用同极性最近的真实边沿，计算带符号模回卷误差`error = circular(Traw - ((Ttrue-epoch) mod 2048000))`。按通道及极性取均值，`offset_ps=round(mean(error))`，Python round在恰好半整数时取最近偶数。未另行剔除离群样本，mask无效帧不属于该通道测量。
原始观察记录、每相位覆盖和样本数量分别在results/calibration/*/*/gate/observations.csv、phase_coverage.csv、fitted_parameters.csv。一个输入事件可产生多个相位有效帧，raw样本数量之和可大于选中输出的1600个边沿。

参数包含公共流水线、输入分发及本实现粗时间参考epoch下的绝对偏移。结构新增一拍为2 ns，但两版绝对参数之差还包含物理路径/clock epoch变化，不能全部解释为公共流水线增量。OLD_VS_NEW_CALIBRATION.csv同时给出相对0°通道偏差，用于分离公共项与相对固定延迟。

| 通道 | 极性 | 新Baseline均值(ps) | 应用参数(ps) | 补偿实现自身拟合(ps) | 样本n(B/C) | 一致 |
|---|---|---:|---:|---:|---:|---|
| 90° | rise | 36010.975610 | 36011 | 36011 | 328/328 | True |
| 90° | fall | 36010.975610 | 36011 | 36011 | 328/328 | True |
| 180° | rise | 35742.000000 | 35742 | 35742 | 320/320 | True |
| 180° | fall | 35742.000000 | 35742 | 35742 | 320/320 | True |
| 270° | rise | 35756.500000 | 35756 | 35756 | 320/320 | True |
| 270° | fall | 35756.500000 | 35756 | 35756 | 320/320 | True |
| 0° | rise | 36081.250000 | 36081 | 36081 | 320/320 | True |
| 0° | fall | 36081.250000 | 36081 | 36081 | 320/320 | True |

先冻结新Baseline的DCP/网表/SDF，再由该实现的独立扫描冻结8参数，随后独立综合Compensated；最后使用补偿实现自身网表/SDF再次扫描，检查与应用参数逐项一致。主验证不反向调整参数。对应SHA在每批input_sha256.json、最终SOURCE_PROVENANCE.json及交付清单中。
补偿实现自身拟合与应用值全部一致：**True**。若为False，Compensation必须FAIL，不把不同实现的偏移混称为同一校准。

10 ps/tap是当前RTL的时间换算系数，校准没有重新拟合bin宽；这不表示每个物理tap的SDF延迟恰好为10 ps。

# 四相TDC固定延迟补偿与实现后验证

**整体验收：FAIL。** 两套真实位流、路由后网表/SDF、独立校准与验证、全部CSV及七类图均已生成；静态setup和20MHz暂定帧连续测量问题尚未解决，不能将精度改善等同于系统通过。

- 25.3ns真实SDF脉宽RMSE：135.6024→53.1472ps，改善60.81%；200/200样本完整。
- 20MHz/50%：143.2690→69.7354ps；200/200完整。10MHz暂定完整帧1056/1056正确配对。
- 两版主验证均3512输入、3509输出、3507正确配对；3个R及2个F缺失造成2个错配，完整20MHz帧指标标N/A。
- Baseline/Compensated WNS分别-0.163/-0.173ns，setup失败端点12/19；hold最小均+0.058ns。
- 8项偏移来自独立800脉冲SDF校准；按0/90/180/270°排列，升/降本批均为34698/34710/34861/34796ps。默认RTL关闭补偿，正式补偿构建由Tcl加载真实参数。

主要文件：

- [完整RMSE/Bias/STD、MaxAbs、有效率与结论](FINAL_RMS_COMPARISON.md)
- [异常事件、短低电平与错误FIFO证据](ANOMALIES.md)
- [校准方法与8参数](CALIBRATION_REPORT.md)
- [静态与动态时序](TIMING_REPORT.md)
- [原始RTL与工程审查](RTL_REVIEW.md)
- [复现与恢复原代码](REPRODUCE.md)
- [Baseline位流](results/baseline/tdc_baseline.bit) / [Compensated位流](results/compensated/tdc_compensated.bit)
- [参数CSV](results/tdc_skew_calibration.csv) / [逐事件比较CSV](results/paired_comparison.csv) / [图表目录](results/figures/)

ATC帧头顺序及对齐是明确的临时假设。SDF为slow/MAX器件模型仿真，不是硅片实测；源码快照、参数与各版本哈希均保留。

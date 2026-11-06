# 时序前后对照

基准为实际AD23生产DCP，不是另一份历史SDF实现。单位ns。

| 实现 | WNS | TNS | WHS | THS |
|---|---:|---:|---:|---:|
|当前生产版|-0.05|-0.166|0.054|0.0|
|本次Debug路由版|-0.164|-0.653|0.054|0.0|

生产版全局负路径来自历史ILA2；核心和调试路径必须分开审查。

| 模块 | 原Setup最差 | Debug Setup最差 | 原Hold最差 | Debug Hold最差 |
|---|---:|---:|---:|---:|
|u_tdc_fine_layer|0.050|0.082|0.108|0.108|
|u_tdc_time_candicate|0.265|0.119|0.119|0.114|
|u_tdc_time_locate|0.293|0.312|0.110|0.148|
|u_tdc_time_merge|0.166|0.113|0.134|0.142|
|u_fifo_tdc_result|0.099|0.073|0.095|0.096|
|u_fifo_tdc_error|0.132|0.055|0.054|0.106|

新增核心负Setup路径数：0。详细起终点见results/after/negative_setup.csv；Hold见negative_hold.csv。

BIT门槛：任何测量核心、影子采集、ILA或Hub路径有负Setup/Hold均停止BIT生成。没有新增false path、multicycle或关闭timing check。

最终状态：TIMING_GATE_FAIL。未生成BIT时不得烧录中间DCP或其他版本替代本任务验收。

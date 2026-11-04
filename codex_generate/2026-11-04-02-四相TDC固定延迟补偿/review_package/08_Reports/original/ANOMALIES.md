# 连续测量异常与FIFO诊断

当前临时协议的帧头在单元起点上升，数据PWM由峰值起始的三角载波自然比较生成，属于中心对齐。二者混合在20MHz帧部分bank边界产生1.293～1.736ns低电平。本实验保留原输入，不根据失败结果重排帧头或更改波形。

## baseline

输入3512，输出3509，正确配对3507；缺失R=[2918, 2984, 3050]、F=[2917, 2983]。

| 无正确配对的输入ID | bank | channel | header | 真实高电平ps | 前一低电平ps |
|---:|---:|---:|---:|---:|---:|
| 2917 | 6 | 63 | -1 | 47335 | 2669 |
| 2918 | 7 | -1 | 0 | 2500 | 1330 |
| 2983 | 7 | 63 | -1 | 47416 | 2581 |
| 2984 | 8 | -1 | 0 | 2500 | 1293 |
| 3050 | 9 | -1 | 0 | 2500 | 1736 |

| 错配输出对应下降沿ID | 实际来源上升沿ID | 实际脉宽ps | 本下降沿输入高电平ps |
|---:|---:|---:|---:|
| 2918 | 2917 | 50900 | 2500 |
| 2984 | 2983 | 50940 | 2500 |

全部业务错误事件：

```json
[
  {
    "time_ps": "238744150",
    "kind": "conflict",
    "code": "1"
  },
  {
    "time_ps": "242044150",
    "kind": "conflict",
    "code": "1"
  },
  {
    "time_ps": "245344150",
    "kind": "conflict",
    "code": "1"
  },
  {
    "time_ps": "245346150",
    "kind": "repeat",
    "code": "1"
  },
  {
    "time_ps": "245358150",
    "kind": "merge",
    "code": "2"
  }
]
```

conflict@238744150ps的前5拍原始帧：`{'time_ps': '238734150', 'coarse': '246', 'mask': '11', 'polarity': '202', 'codes': '704645666'}`。
conflict@242044150ps的前5拍原始帧：`{'time_ps': '242034150', 'coarse': '872', 'mask': '11', 'polarity': '202', 'codes': '704646694'}`。
conflict@245344150ps的前5拍原始帧：`{'time_ps': '245334150', 'coarse': '474', 'mask': '9', 'polarity': '194', 'codes': '704643078'}`。

独立错误FIFO诊断：
```json
{
  "status": "PASS",
  "scope": "post-route directed error-FIFO reproduction; not a precision-validation replacement",
  "source_error_codes": [
    2
  ],
  "read_100MHz_error_codes": [
    2
  ],
  "result_fifo_sequence_equal": true,
  "stimulus_sha256": "1f18db05d3dddf0fbae38731483fe4c8ec0760f84e4d0967aa41a768d9af169d"
}
```

## compensated

输入3512，输出3509，正确配对3507；缺失R=[2918, 2984, 3050]、F=[2917, 2983]。

| 无正确配对的输入ID | bank | channel | header | 真实高电平ps | 前一低电平ps |
|---:|---:|---:|---:|---:|---:|
| 2917 | 6 | 63 | -1 | 47335 | 2669 |
| 2918 | 7 | -1 | 0 | 2500 | 1330 |
| 2983 | 7 | 63 | -1 | 47416 | 2581 |
| 2984 | 8 | -1 | 0 | 2500 | 1293 |
| 3050 | 9 | -1 | 0 | 2500 | 1736 |

| 错配输出对应下降沿ID | 实际来源上升沿ID | 实际脉宽ps | 本下降沿输入高电平ps |
|---:|---:|---:|---:|
| 2918 | 2917 | 50998 | 2500 |
| 2984 | 2983 | 51038 | 2500 |

全部业务错误事件：

```json
[
  {
    "time_ps": "238744150",
    "kind": "conflict",
    "code": "1"
  },
  {
    "time_ps": "242044150",
    "kind": "conflict",
    "code": "1"
  },
  {
    "time_ps": "245344150",
    "kind": "conflict",
    "code": "1"
  },
  {
    "time_ps": "245346150",
    "kind": "repeat",
    "code": "1"
  },
  {
    "time_ps": "245358150",
    "kind": "merge",
    "code": "2"
  }
]
```

conflict@238744150ps的前5拍原始帧：`{'time_ps': '238734150', 'coarse': '246', 'mask': '11', 'polarity': '202', 'codes': '704645666'}`。
conflict@242044150ps的前5拍原始帧：`{'time_ps': '242034150', 'coarse': '872', 'mask': '11', 'polarity': '202', 'codes': '704646694'}`。
conflict@245344150ps的前5拍原始帧：`{'time_ps': '245334150', 'coarse': '474', 'mask': '9', 'polarity': '194', 'codes': '704643078'}`。

独立错误FIFO诊断：
```json
{
  "status": "PASS",
  "scope": "post-route directed error-FIFO reproduction; not a precision-validation replacement",
  "source_error_codes": [
    2
  ],
  "read_100MHz_error_codes": [
    2
  ],
  "result_fifo_sequence_equal": true,
  "stimulus_sha256": "1f18db05d3dddf0fbae38731483fe4c8ec0760f84e4d0967aa41a768d9af169d"
}
```

同帧同时含下一周期0°上升候选与90°/180°下降候选，原candidate逻辑明确判polarity_conflict并丢帧。前两个边界丢失上一数据单元F和下一帧头R，留下的帧头F与旧R形成约50.9ns错误宽度；第三个边界出现孤立F错误2。该原因有真实raw帧及控制错误日志支持，不是关联脚本错位。

独立FIFO诊断只将原ID3047～3054片段平移235160000ps（100MHz与500MHz整周期），保持高低间隔与相位，预期8输入产生7脉宽及一个错误2；两套位流均直接核对500MHz错误入队与100MHz错误读出。它不替代原3512输入验证，不将预期故障当作正常帧通过。

下一步应先确认真实ATC帧头与数据的对齐协议。若真实输入允许同一采样帧含两个异极性边沿，需要独立设计多事件帧缓冲/排序并保留采样帧粗时间标签，再重新实现和独立校准；固定时间戳偏移无法恢复被候选层丢弃的事件。

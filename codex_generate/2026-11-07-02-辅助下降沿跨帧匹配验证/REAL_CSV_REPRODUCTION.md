# 真实错误复现与边界定位

源数据是任务01的`results/hardware_debug_04/TRIGGER_A.csv`，SHA256见`inputs/SOURCE.json`。本任务保留逐字节副本。原CSV第二行所有探针为UNSIGNED；解析按该行声明进行。没有新采集或改写实验数据。

## 位序与观测延迟

`debug_raw_q`低到高依次为90°、180°、270°、0°，每包10bit=`{type[1:0],code[7:0]}`。辅助四位低到高同样为90°、180°、270°、下一周期0°；`aux_fall_match[3]`对应0°。final_types低到高相同。原CSV的type=10是下降，11是上升，00无效；不能把十进制总线字符串直接看成二进制。

这些信号由同一0°时钟的只读影子寄存器观察，随后经过相同ILA输入流水。影子与ILA的公共延迟不额外加到某一条通路。`tb_replay.sv`在下一次上升沿前读取组合边界，先驱动实际ordered_samples与相位包，再由原RTL生成slot、history、claimed、match、sync及后端输出。未强制match或final_type。

## 逐拍事实

| 样本 | 真实信号 | 原RTL结果 |
|---:|---|---|
| 728 | fall_slots=1000，fall_previous=0000 | 辅助有序采样检测到了下降事件；原任务描述把这里写成previous，需纠正 |
| 730 | fall_now=1000，无相应有效下降包 | slots经过ALIGN_CYCLES=2到达now |
| 731 | fall_now=0000，fall_previous=1000，claimed=0；0°type=10/code=13 | match=0111，bit3=0；final_type0=00 |
| 732 | sync_edge_valid=0000 | 没有下降沿进入候选选择 |
| 737/742 | candidate/timestamp没有该下降输出 | 确认门控丢失向后传播 |
| 762/767/768 | 新上升候选/上升timestamp/重复上升错误 | 原配对机按缺少下降沿后的规则报错 |

共完成13,209项有效字段逐拍核对，Baseline复现成功；首20个边界预热点不用于等价检查。`results/EVENT_TRACE.csv`保存1024点解码，`KEY_WINDOW.csv`保存717～768窗口。

## 哪一级错位

可观测边界上，辅助事件到达now的样本730比0°有效包样本731早一个500MHz周期，即名义2ns；不是“ILA让一条通路额外延迟一拍”。历史推进正确：slots728→now730→previous731。首次可见功能丢失是731的0°辅助匹配范围：当前逻辑只允许0°使用now，排除了尚未claimed的previous[3]。

原窗口分别是90°=`now[0]|previous[3:1]`，180°=`now[1:0]|previous[3:2]`，270°=`now[2:0]|previous[3]`，0°=`|now`。每相有自己的2ns滑动窗口。不能从这一例推出整个辅助下降通路都错一拍。统一推迟一拍的方案C在相同真实记录中恢复了731，却丢掉另一正常下降，并在完整理想RTL测试中丢掉全部下降，因此否决。

正常样本31中同样的辅助previous[3]由270°有效下降包接走；异常731只有0°下降包有效，270°为type00/code62。下降数值合法范围是MIN_VALID_TAP≤code<64，不能只因62而声称越界。缺少thermo、detected_type、raw_edge_type、encoder_ready观察，无法解释270°为什么无效。

## 物理证据的边界

从本次上板Debug DCP只读提取的`results/input_paths/INPUT_PATHS.csv`显示：pwm_in到辅助0°meta/D最大/最小数据延迟为2.920/1.291ns，到TDL0首tap采样D为4.805/2.243ns。两条支路确有不同传播路径；同角估计差值为1.885/0.952ns。它支持检查分发延迟与跨帧窗口，不能当成示波器测得的差值，也不能单凭端点最大/最小路径差证明实际输入每次固定偏移2ns。

因此已充分确认这一次的数字门控丢失机制。尚未证明最早的物理相位偏移来自哪一级采样，不能声称新增流水线必然写错，也不能排除模拟输入振铃或把全部上板错误归为同一原因。

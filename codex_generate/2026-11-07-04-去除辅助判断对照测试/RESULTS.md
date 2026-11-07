# NoAux：约定范围验收通过

基于 `d8b691b65316246567696cdbf8abd4e0f30950ee`。独立版本新增编译期 `ENABLE_AUX_CONFIRM`，默认1保留辅助确认，NoAux构建固定0。仅修改fine_layer与meas_top，原辅助代码保留；正式生产RTL、旧Corrected BIT及板上配置未改，本轮未烧录FPGA或Flash。

## 保持的功能

NoAux使用四相TDL已通过原极性检测和code_in_range筛选的类型，旁路辅助门控；复用既有确认级的类型寄存器，与细码、valid及ready同帧同拍。相对Corrected新增延迟0，Locate五级及粗计数影子保留。Candidate优先级、Merge、FIFO、8参数及TDL编码/CARRY4子模块全文不变。范围仍是上升1～60、下降5～63。

## RTL与用户确认范围

1024组码值/极性、2592组旁路独立性/流水检查通过；三完整实例对照中，AuxOn与冻结原版逐周期一致。六固定PWM工况每项200脉冲，三组模型中两版全部正确配对。

额外ATC短低间隔测试在250ps/级理想模型下两版同样3次冲突、3次错配，原完整RTL_GATE的FAIL及全部CSV不改。用户随后明确接受“高低电平均≥2ns”。原真实输入含1845/1330/1293/1736ps四处短低间隔，涉及8个脉冲；包括原本通过的一对也按同规则列为范围外。范围内3504个脉冲，六组RTL均通过。范围只依据输入时刻，不参考测量结果，不修改波形或阈值。见SCOPE_DECISION.md。

## 实现与时序

Vivado 2022.2、XC7K325T-FFG900-2、500MHz四相及100MHz原时钟、AD23输入。一次综合/布局布线；增量复用原DCP及578个FIFO原语位置，四个XCI逐字节不变。核心Setup最差+0.099ns、Hold最差+0.054ns，负端点均0。全局WNS/TNS=-0.050/-0.166ns、WHS/THS=+0.054/0.000ns，保留14个历史ILA2非反馈负端点，没有新增时序例外或降低频率。详见TIMING_REPORT.md及原报告。

## XSim MAX-SDF

本次最终路由DCP导出slow/MAX SDF与网表，官方simprims_ver/secureip，严格全局注释成功、零未匹配诊断，全部时序检查开启。请求项计数不是逐项成功率读回。最小112脉冲（含恰好2ns高低间隔）正确112/112；原完整3512激励没有删改，范围内正确3504/3504，范围门=True。

完整3512的原判定单独保留：正确3510/3512、错配0、完整MAX_SDF_pass=False。完整NoAux另有2次孤立下降（事件2918/2984）、0次重复上升和0次时间越界；均已按实际事件ID及原Merge流水重放核对，详见SDF_ERROR_ATTRIBUTION.md。不把范围门结果写成原完整RTL PASS，不删范围外失败；范围内任何漏沿、重复、错配、越界、未知归属、FIFO问题或未分类核心告警都会阻断BIT。全部细节见SCOPED_SUMMARY.json与SUMMARY.json。

## 同输入SDF误差比较

| 版本 | N | Bias ps | RMSE ps | 样本STD ps | MaxAbs ps |
|---|---:|---:|---:|---:|---:|
| aux_on | 3504 | -0.521 | 65.262 | 65.269 | 189 |
| noaux | 3504 | 0.801 | 64.581 | 64.586 | 199 |

AuxOn复用指定提交已完成的Corrected SDF，DCP/波形/参数/角及文件校验见AUX_ON_SDF_REFERENCE.json，不重复仿真或打包大型旧文件。统计基于相同范围内输入ID；SDF_COMPARISON.csv另列全部关联输出（含错配）和正确配对子集。Bias=平均误差，RMSE=sqrt(mean(error²))，STD使用N−1，不除sqrt(2)。混合脉宽误差STD不等于单一脉宽的重复性；这是仿真统计，不是上板实测。

## 交付

NoAux BIT/LTX交付状态：True。文件在implementation/NoAux.bit及NoAux.ltx，由同一验收DCP导出；未烧录。 Corrected.bit原样保留。此为辅助判断旁路的实验对照，不宣称已解决上板152/37残留错误。须经后续用户授权的上板A/B才能评价硬件效果。

两次准备期失败（单元复位预热、VVP中文plusarg路径）日志保留，后续只修正测试平台或运行路径，RTL/激励未改。所有原始CSV、日志、时序、实现文件附SHA256。

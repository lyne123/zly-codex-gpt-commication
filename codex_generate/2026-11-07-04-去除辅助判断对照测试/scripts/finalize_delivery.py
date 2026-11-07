"""完整仿真结束后整理真实结果，区分原完整FAIL与用户范围门；不修改正式RTL。"""
from pathlib import Path
import hashlib,json,shutil,subprocess
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_noaux_20261107_04'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
scope=load(TASK/'results/SCOPED_RTL_GATE.json')
minimal=load(TASK/'results/sdf/noaux/minimal/SCOPED_SUMMARY.json')
full=load(TASK/'results/sdf/noaux/full/SCOPED_SUMMARY.json')
native=load(TASK/'results/sdf/noaux/full/SUMMARY.json')
assert load(TASK/'results/sdf/noaux/full/RUN_MANIFEST.json')['completed']
bit=TASK/'implementation/BIT_MANIFEST.json'
passed=scope['pass_all'] and minimal['pass_all'] and full['pass_all']
if passed:assert bit.exists() and load(bit)['pass_all'],'通过后须先导出验收BIT'
else:assert not (TASK/'implementation/NoAux.bit').exists(),'失败不允许交付BIT'
frozen=load(TASK/'inputs/SOURCE.json')
for name,d in frozen['production_RTL_sha256'].items():assert sha(ROOT/'fpga_tdc_v3_cal_rtl'/name)==d
for name,d in frozen['candidate_RTL_sha256'].items():assert sha(TASK/'rtl'/name)==d
for name,d in frozen['inputs_sha256'].items():assert sha(TASK/'inputs'/name)==d
assert sha(TASK/'results/RTL_GATE.json')==scope['original_RTL_GATE_sha256']
old=ROOT/'codex_generate/2026-11-07-03-辅助跨帧匹配时序优化/implementation/Corrected.bit'
assert sha(old)=='59f1630048ade43ec5c0d7560c1e756ba664421e83e53c84028ca4956a61f523'
subprocess.run(['python',str(TASK/'scripts/compare_sdf.py')],check=True)
comparison=load(TASK/'results/SDF_COMPARISON.json')
for name in ['build_noaux.log','build_noaux.jou']:shutil.copy2(WORK/name,TASK/'logs'/name)
for p in (WORK/'accepted_bit_export').glob('*.log'):shutil.copy2(p,TASK/'logs'/('bit_'+p.name))
v=load(TASK/'VALIDATION.json')
v.update(status='PASS_IN_USER_SCOPE' if passed else 'FAIL_IN_USER_SCOPE',scope_clarification_pending=False,
    scope_user_confirmed=True,scope_high_min_ps=2000,scope_low_min_ps=2000,scope_pulses=3504,
    scoped_RTL_matrix_pass=True,original_complete_RTL_matrix_pass=False,
    synthesis='COMPLETED',implementation='COMPLETED',core_timing='PASS',MAX_SDF='COMPLETED',
    MAX_SDF_minimal=minimal,MAX_SDF_full_scoped=full,MAX_SDF_full_original=native,
    NoAux_BIT_generated=passed,NoAux_LTX_generated=passed,NoAux_LTX_delivered=passed,
    FPGA_programmed=False,Corrected_BIT_unchanged=True,production_RTL_unchanged=True,
    DCP_sha256=sha(TASK/'implementation/NoAux_routed.dcp'),
    candidate_RTL_sha256=frozen['candidate_RTL_sha256'],archive_ready=True)
save(TASK/'VALIDATION.json',v)
im=load(TASK/'implementation/IMPLEMENTATION_MANIFEST.json')
im.pop('bit_not_yet_generated',None);im['NoAux_BIT_generated']=passed
if passed:im['BIT_MANIFEST']=load(bit)
save(TASK/'implementation/IMPLEMENTATION_MANIFEST.json',im)
metrics=[r for r in comparison['metrics'] if r['population']=='same_input_scope_common_ID' and r['group']=='all']
table=['| 版本 | N | Bias ps | RMSE ps | 样本STD ps | MaxAbs ps |','|---|---:|---:|---:|---:|---:|']
for r in metrics:table.append(f"| {r['mode']} | {r['n']} | {r['bias_ps']:.3f} | {r['rmse_ps']:.3f} | {r['std_sample_ps']:.3f} | {r['max_abs_ps']} |")
title='约定范围验收通过' if passed else '约定范围验收未通过'
(TASK/'RESULTS.md').write_text(f'''# NoAux：{title}

基于 `d8b691b65316246567696cdbf8abd4e0f30950ee`。独立版本新增编译期 `ENABLE_AUX_CONFIRM`，默认1保留辅助确认，NoAux构建固定0。仅修改fine_layer与meas_top，原辅助代码保留；正式生产RTL、旧Corrected BIT及板上配置未改，本轮未烧录FPGA或Flash。

## 保持的功能

NoAux使用四相TDL已通过原极性检测和code_in_range筛选的类型，旁路辅助门控；复用既有确认级的类型寄存器，与细码、valid及ready同帧同拍。相对Corrected新增延迟0，Locate五级及粗计数影子保留。Candidate优先级、Merge、FIFO、8参数及TDL编码/CARRY4子模块全文不变。范围仍是上升1～60、下降5～63。

## RTL与用户确认范围

1024组码值/极性、2592组旁路独立性/流水检查通过；三完整实例对照中，AuxOn与冻结原版逐周期一致。六固定PWM工况每项200脉冲，三组模型中两版全部正确配对。

额外ATC短低间隔测试在250ps/级理想模型下两版同样3次冲突、3次错配，原完整RTL_GATE的FAIL及全部CSV不改。用户随后明确接受“高低电平均≥2ns”。原真实输入含1845/1330/1293/1736ps四处短低间隔，涉及8个脉冲；包括原本通过的一对也按同规则列为范围外。范围内3504个脉冲，六组RTL均通过。范围只依据输入时刻，不参考测量结果，不修改波形或阈值。见SCOPE_DECISION.md。

## 实现与时序

Vivado 2022.2、XC7K325T-FFG900-2、500MHz四相及100MHz原时钟、AD23输入。一次综合/布局布线；增量复用原DCP及578个FIFO原语位置，四个XCI逐字节不变。核心Setup最差+0.099ns、Hold最差+0.054ns，负端点均0。全局WNS/TNS=-0.050/-0.166ns、WHS/THS=+0.054/0.000ns，保留14个历史ILA2非反馈负端点，没有新增时序例外或降低频率。详见TIMING_REPORT.md及原报告。

## XSim MAX-SDF

本次最终路由DCP导出slow/MAX SDF与网表，官方simprims_ver/secureip，严格全局注释成功、零未匹配诊断，全部时序检查开启。请求项计数不是逐项成功率读回。最小112脉冲（含恰好2ns高低间隔）正确{minimal['scope_correct_pulses']}/112；原完整3512激励没有删改，范围内正确{full['scope_correct_pulses']}/{full['scope_pulses']}，范围门={full['pass_all']}。

完整3512的原判定单独保留：正确{native['correct_pairs']}/3512、错配{native['mispairs']}、完整MAX_SDF_pass={native['MAX_SDF_pass']}。完整NoAux另有2次孤立下降（事件2918/2984）、0次重复上升和0次时间越界；均已按实际事件ID及原Merge流水重放核对，详见SDF_ERROR_ATTRIBUTION.md。不把范围门结果写成原完整RTL PASS，不删范围外失败；范围内任何漏沿、重复、错配、越界、未知归属、FIFO问题或未分类核心告警都会阻断BIT。全部细节见SCOPED_SUMMARY.json与SUMMARY.json。

## 同输入SDF误差比较

{chr(10).join(table)}

AuxOn复用指定提交已完成的Corrected SDF，DCP/波形/参数/角及文件校验见AUX_ON_SDF_REFERENCE.json，不重复仿真或打包大型旧文件。统计基于相同范围内输入ID；SDF_COMPARISON.csv另列全部关联输出（含错配）和正确配对子集。Bias=平均误差，RMSE=sqrt(mean(error²))，STD使用N−1，不除sqrt(2)。混合脉宽误差STD不等于单一脉宽的重复性；这是仿真统计，不是上板实测。

## 交付

NoAux BIT/LTX交付状态：{passed}。{'文件在implementation/NoAux.bit及NoAux.ltx，由同一验收DCP导出；未烧录。' if passed else '没有生成最终NoAux BIT，不强行交付。'} Corrected.bit原样保留。此为辅助判断旁路的实验对照，不宣称已解决上板152/37残留错误。须经后续用户授权的上板A/B才能评价硬件效果。

两次准备期失败（单元复位预热、VVP中文plusarg路径）日志保留，后续只修正测试平台或运行路径，RTL/激励未改。所有原始CSV、日志、时序、实现文件附SHA256。
''',encoding='utf-8')
(TASK/'README.md').write_text(f'''# 2026-11-07-04 去除辅助判断对照测试

**{title}**，高电平和相邻低电平均≥2ns。NoAux BIT生成状态：{passed}；本轮未烧录FPGA/Flash，正式RTL与Corrected BIT保留。

- [详细结果](RESULTS.md)、[范围确认](SCOPE_DECISION.md)、[时序报告](TIMING_REPORT.md)、[机器状态](VALIDATION.json)。
- `rtl/`：完整参数化候选；默认ENABLE_AUX_CONFIRM=1，NoAux编译固定0。`reference/rtl/`及`RTL.diff`保留原版和差异。
- 原阈值上升1～60、下降5～63，8参数不变，确认级保留，相对Corrected新增延迟0。
- 核心Setup/Hold +0.099/+0.054ns；历史14条ILA负端点保留，全部实际NoAux报告在results/timing。
- `results/RTL_GATE.json`保留原完整补充FAIL；`SCOPED_RTL_GATE.json`是用户确认范围的新判定。没有改波形或删异常。
- `results/sdf/noaux/`：最小和完整原始CSV、完整压缩日志、注释证据、原完整与范围两份摘要。
- `results/SDF_COMPARISON.csv`：相同输入ID的AuxOn/NoAux误差比较；旧AuxOn文件通过不可变提交和SHA256引用，不重复打包。
- `implementation/`：本次路由/综合DCP、SDF、网表、有效约束，{'以及NoAux.bit/NoAux.ltx。' if passed else '没有最终BIT。'}大文件使用Git LFS。
- `inputs/`、`sim/`、`scripts/`、`results/rtl/`保存全部必要输入、验证程序和失败记录。完整SDF日志无损压缩，原日志位置及原始SHA见RUN_MANIFEST。
- `FILE_LIST.csv`及`SHA256SUMS.txt`为清单与校验，均不含自身，避免循环。

原完整RTL补充模型的短间隔FAIL仍保留；通过范围门不等于无条件支持<2ns输入。未重新校准或拟合参数，也没有把数字验收结果当作上板修复结论。
''',encoding='utf-8')
t=TASK/'TIMING_REPORT.md';s=t.read_text(encoding='utf-8').replace('完整3512激励仍在运行。','完整3512激励已执行完成。').replace('完整仿真完成前不生成BIT；最终状态以VALIDATION及各SDF摘要为准。','BIT交付状态以VALIDATION及各SDF摘要为准。')
s+='\n## 最终SDF状态\n\n最小范围门='+str(minimal['pass_all'])+'；完整范围门='+str(full['pass_all'])+'；原完整SDF门='+str(native['MAX_SDF_pass'])+'。实际记录与校验均已归档，未烧录。\n';t.write_text(s,encoding='utf-8')
attrs=TASK/'.gitattributes';s=attrs.read_text(encoding='ascii')
if 'implementation/post_route_timing.v' not in s:s+='implementation/post_route_timing.v filter=lfs diff=lfs merge=lfs -text\n';attrs.write_text(s,encoding='ascii')
print('NOAUX_DELIVERY_FINALIZED scoped_pass=',passed,'NoAux_bit=',passed,'hardware_programmed=False',flush=True)

"""按实际失败门限生成停止报告，保留所有输入和失败证据；正式RTL不得变化。"""
from pathlib import Path
import csv,difflib,hashlib,json,re,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
source=json.loads((TASK/'inputs/SOURCE.json').read_text(encoding='utf-8'))
for name,digest in source['formal_RTL_sha256'].items():
    assert sha(ROOT/'fpga_tdc_v3_cal_rtl'/name)==digest,name
    assert sha(TASK/'original/rtl'/name)==digest,name
assert sha(TASK/'inputs/TRIGGER_A.csv')==source['real_CSV_sha256']
gates={}
for label,folder,log in [('E_guarded','implementation','build_candidate'),('F_factored','implementation_F','build_factored')]:
    src=WORK/folder;dst=TASK/'results'/folder
    gate=(src/'TIMING_GATE.txt').read_text();assert 'core_negative_endpoints=0' not in gate,'此报告只用于实际时序失败停止情形'
    gates[label]=dict(line.split('=',1) for line in gate.splitlines() if '=' in line)
    dst.mkdir(exist_ok=True)
    for sub in ['before','after']:
        if (src/sub).exists():shutil.copytree(src/sub,dst/sub,dirs_exist_ok=True)
    for name in ['corrected_routed.dcp','post_route_max.sdf','post_route_timing.v','Corrected.ltx','effective_constraints.xdc','TIMING_GATE.txt']:
        shutil.copy2(src/name,dst/name)
    for ext in ['log','jou']:shutil.copy2(WORK/(log+'.'+ext),TASK/'logs'/(log+'.'+ext))
for name in ['probe_input_paths.log','probe_input_paths.jou']:
    if (WORK/name).exists():shutil.copy2(WORK/name,TASK/'logs'/name)
for ip in ['clk_wiz_0','fifo_tdc_result','ila_2','ila_3']:
    dest=TASK/'inputs/ip'/ip;dest.mkdir(parents=True,exist_ok=True)
    shutil.copy2(WORK/f'registered/aux_compensated.srcs/sources_1/ip/{ip}/{ip}.xci',dest/(ip+'.xci'))
external={}
for role,p in {
    'production_baseline_bit':ROOT/'codex_generate/2026-11-06-02-PWM-AD23/results/TDC_Compensated_ILA100M_PWM_AD23.bit',
    'production_baseline_dcp':WORK/'production_AD23.dcp',
    'previous_debug_bit':ROOT/'codex_generate/2026-11-07-01-上板边沿配对错误ILA定位/ILA_DEBUG.bit',
    'previous_debug_dcp':WORK/'reference_debug.dcp',
}.items():
    external[role]=dict(path=str(p),size=p.stat().st_size,sha256=sha(p),packaged=False,reason='历史原件保留；本轮无可采用修复，不重复上传旧大文件')
assert external['production_baseline_bit']['sha256']=='c3c5d5e5afcdab910a59da3d7a1897f1e25450266621569cf50ad819f824a35a'
assert external['previous_debug_bit']['sha256']=='4df6b364eda1511abf910637ad8edb64bc518cb092de91f53e7a567736ed58e7'
dump(TASK/'inputs/EXTERNAL_REFERENCES.json',external)
diff=[]
for name in source['formal_RTL_sha256']:
    a=(TASK/'original/rtl'/name).read_text(encoding='utf-8');b=(TASK/'variants/F_factored'/name).read_text(encoding='utf-8')
    diff.extend(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='baseline/'+name,tofile='candidate_NOT_ADOPTED/'+name))
(TASK/'RTL.diff').write_text(''.join(diff),encoding='utf-8')
(TASK/'FORMAL_RTL.diff').write_bytes(b'')
pwm=json.loads((TASK/'results/PWM_COMPARISON.json').read_text(encoding='utf-8'))
with (TASK/'results/SCHEME_STATISTICS.csv').open('w',encoding='utf-8',newline='') as f:
    fields=['experiment','pulses','rises','falls','missing_rise','missing_fall','fall_detection_rate','duplicate_edges','mismatched_pairs','double_rise','orphan_fall','max_abs_width_error_ps','functional_pass']
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for name,r in pwm.items():
        row={k:r[k] for k in fields if k in r};row.update(experiment=name,fall_detection_rate=(r['pulses']-r['missing_fall'])/r['pulses']);w.writerow(row)
def timing(p):
    t=p.read_text();m=re.search(r'WNS\(ns\).*?\n\s*-+.*?\n\s*([-\d.]+)\s+([-\d.]+)\s+\d+\s+\d+\s+([-\d.]+)\s+([-\d.]+)',t,re.S)
    assert m,p
    return list(map(float,m.groups()))
before=timing(TASK/'results/implementation/before/timing_summary.rpt')
e=timing(TASK/'results/implementation/after/timing_summary.rpt');f=timing(TASK/'results/implementation_F/after/timing_summary.rpt')
assert before==[-.05,-.166,.054,0.0] and e[0]==-.729 and f[0]==-.579
validation=dict(status='STOP_NO_ACCEPTED_FIX',reason='功能候选通过，但两次独立实现均引入核心Setup违例；正式RTL保持Baseline',
    real_CSV_reproduced=True,real_CSV_equivalence_checks=13209,observed_aux_to_candidate_lag_cycles=1,nominal_cycle_ps=2000,
    physical_origin_of_phase_skew='尚未充分观测，不认定统一新增流水线错误',
    formal_RTL_modified=False,formal_RTL_sha256=source['formal_RTL_sha256'],compensation_recalculated=False,
    adopted_scheme='A_baseline',candidate='F_factored_NOT_ADOPTED',
    E_F_RTL_output_tests='PASS：每模型1344脉冲×3模型，全部参考边沿配对、错误和FIFO检查通过',
    F_guard_properties_cases=262144,F_guard_properties_pass=True,
    strict_onehot_confirmation='未满足：真实记录Baseline/E/F均有21个多相候选帧；只证明最终未重复输出，未修改选择器',
    implementation_gates=gates,baseline_global_timing=before,E_global_timing=e,F_global_timing=f,
    corrected_SDF_generated=True,SDF_simulation='NOT_EXECUTED_CORE_TIMING_GATE_FAILED',SDF_annotation='NOT_EXECUTED',
    Baseline_bit_generated_or_copied=False,Corrected_bit_generated=False,FPGA_programmed=False,
    previous_bits_unchanged=True,failed_logs_preserved=True,source_commits=dict(analysis=source['analysis_commit'],formal=source['formal_source_commit']))
dump(TASK/'results/VALIDATION.json',validation)
(TASK/'TIMING_BEFORE_AFTER.md').write_text('''# 核心时序验收：FAIL，停止采用

Vivado2022.2，XC7K325T-FFG900-2，500MHz；参考是实际AD23生产实现，不是历史AF20 SDF实现。每个候选独立实现一次；F针对E已定位的晚到控制负路径作等价分解，并非反复调整实现种子。

| 实现 | 全局WNS ns | 全局TNS ns | WHS ns | THS ns | 核心最差Setup ns | 核心负端点 |
|---|---:|---:|---:|---:|---:|---:|
| 冻结AD23 Baseline | -0.050 | -0.166 | +0.054 | 0 | +0.050 | 0 |
| E 全局保护回退 | -0.729 | -6.418 | +0.054 | 0 | -0.729 | 12 |
| F 等价余因子 | -0.579 | -5.560 | +0.054 | 0 | -0.579 | 14 |

Baseline的14个历史负端点都在ILA2。E新增12个核心端点，核心TNS=-6.252ns；F新增14个核心端点，核心TNS=-5.394ns。它们不能按历史ILA违例忽略。所有版本Hold负端点为0。

E最差：pack270_to90_reg[9]（90°）→3级LUT6→sync_edge_polarity_reg[3]（0°），要求1.5ns，数据路径1.771ns，其中布线1.419ns。F将晚到类型控制限于末级选择，但最差转移到g_align[2].rise_q_reg[1]→3级LUT6+末级LUT5→sync_edge_valid_reg[3]，要求2ns，数据路径2.528ns，布线2.069ns；另外pack270→claimed两个端点分别-0.123/-0.081ns。

没有新增false path、关闭时序检查、修改频率、改补偿参数或增加测量流水级。没有为ILA历史违例做优化。保持正式Baseline，不再进行无依据的第三次实现。

完整报告、核心模块最差路径和负端点CSV见results/implementation及results/implementation_F。两次实现导出的slow/MAX SDF、网表与最终路由DCP用于审查失败实现；SDF尚未注释或执行仿真，不能说后仿通过。综合/布线原始日志保存在logs/。
''',encoding='utf-8')
(TASK/'README.md').write_text('''# 2026-11-07-02 辅助下降沿跨帧匹配验证

**结论：真实错误已逐拍复现；确认0°候选被前帧辅助匹配范围阻断。可靠正式修复未完成，保留Baseline，不生成新BIT。**

来源：调试结果Commit `2e9cf594aed51c67d48c090fdea9b92125f7822b`；正式RTL来源 `ba978229094a8621b30770177727d8e70b831a74`。目标XC7K325T-FFG900-2，Vivado2022.2。归档分支`codex/2026-11-07-02-aux-fall-slot-alignment`，不合并main。

## 实际结果

1. 原RTL边界重放与真实CSV的13,209项核对一致。辅助fall_now在730，0°下降包在731，相差一个500MHz周期（2ns）；此时事件已在previous[3]且未claimed，原0°只接受now，导致final_type0=00。后端配对错误是结果。
2. 比较A/B/C/D/E/F。B恢复该例但改变18次原选择；C新增正常下降丢失；D保守局部恢复但传播压力下仍不完整。E/F在三组功能模型下各1344脉冲全部正确，恢复真实丢失下降且不改变原有效帧，但实际核心时序失败：E -0.729ns，F -0.579ns。
3. **最终采用A，正式5个RTL逐字节保持不变。** 所有候选位于variants/，不作为生产版本。8个补偿参数、TDL、粗/细测计算、FIFO、候选选择模块和配对状态机均未修改。
4. SDF与实现后网表已经导出用于审查；核心时序门失败，未进行SDF注释/仿真。未生成或复制Baseline.bit，未生成Corrected.bit，未烧录。原生产与Debug BIT均保持原SHA256，位置见inputs/EXTERNAL_REFERENCES.json。
5. 原设计会在一帧确认多个相位候选，再择一输出。真实记录A/E/F均有21个这样的帧。本轮验证最终重复输出为0，不声称confirm层严格onehot；这一字面验收项未实现，也未改动选择算法来追求它。

## 查阅顺序

- REAL_CSV_REPRODUCTION.md：位序、观测延迟、731第一次可见丢失及尚缺证据。
- SCHEME_COMPARISON.md：所有方案、错误计数、归属约束、功能测试定义。
- TIMING_BEFORE_AFTER.md：两次失败实现及实际核心路径。
- results/VALIDATION.json：最终机器可读状态；results/SCHEME_STATISTICS.csv：18组完整RTL比较。
- inputs/TRIGGER_A.csv：原始上板CSV；results/replay/：六方案边界重放；results/pwm/：全链路功能CSV、日志、参考事件配对。
- original/rtl/：完整原正式RTL；variants/：完整独立候选；RTL.diff：未采用F相对Baseline；FORMAL_RTL.diff为空，表示正式无变化。
- results/implementation{,_F}/：失败候选路由DCP、slow/MAX SDF、网表、约束与时序报告；logs/：完整失败日志。文件名corrected_routed及Corrected.ltx来自导出脚本，只是候选命名，**不是验收通过的Corrected版本**。

## 复现

需要Python3.13（标准库）、Icarus Verilog及Vivado2022.2。脚本默认Icarus位于F:/iverilog/bin、Vivado位于F:/Xilinx/Vivado/2022.2/bin；迁移电脑时仅调整工具位置，不调整激励或参数。所有工作目录使用真实ASCII路径，禁止创建虚拟盘符。

1. 校验SHA256SUMS.txt；检查inputs/SOURCE.json。已保存的结果不要覆盖；在独立工程副本中复现。
2. 运行scripts/materialize_runtime.py，从冻结副本建立codex_generate/.vivado_work/tdc_auxfall_20261107_02。
3. 运行scripts/analyze_capture.py解析真实CSV；运行scripts/replay.py重放A/B/C/D。通过环境变量TDC_COMPARE_VARIANTS=E_guarded或F_factored分别运行其重放。
4. 同样设置TDC_COMPARE_VARIANTS后运行scripts/test_pwm.py；它会拒绝覆盖已有运行CSV。scripts/check_guard.py默认E，设置TDC_GUARD_VARIANT=F_factored检查F。scripts/check_equivalence.py检查E/F的19个输出CSV完全一致。
5. inputs/ip/保留原4个XCI；inputs/combine_AD23.xdc与compensation_params.tcl保持原样。scripts/build_candidate.tcl及build_factored.tcl保存实际实现流程，注册IP/OOC缓存和AD23参考DCP使用inputs/EXTERNAL_REFERENCES.json的旧原件。缓存只是加速，未列为实验数据。运行前按原脚本把这些输入复制到同名ASCII运行目录；分别执行Vivado batch。这两次实现预期以CORE_TIMING_FAIL结束，不应绕过门限生成BIT。
6. scripts/run_sdf.py与sim/tb_sdf.sv仅是已准备但未执行的后续方案；它会检查核心门限，当前失败实现不允许启动。无SDF PASS或注释成功率可报告。

## 尚缺证据与最小后续方向

数字确认门控机制已确认；尚缺270°编码前thermo/raw_edge_type/ready和实际输入模拟波形，不能认定270°type00的具体物理原因，不能证明新增流水线统一错一拍，也不能排除所有毛刺。建议下一步只在现有辅助history流水中预计算所需事件资格，减少500MHz末级全局归约及晚到pack270扇出，并先做等价/时序评估；本任务未实施该结构调整。可靠修复还须通过核心时序、SDF及真实上板回归后才能采用。

本任务没有修改任何真实实验数据，没有重校准，没有覆盖原生产或Debug文件。SHA256清单覆盖全部归档输入、代码、CSV、日志和报告；未上传的旧原件有明确路径、大小与哈希，不是遗漏本次证据。
''',encoding='utf-8')
(TASK/'RESULTS.md').write_text('''# 最终验收：STOP_NO_ACCEPTED_FIX

真实上板错误复现：PASS，13,209项实际RTL核对。数字丢失机制确认：辅助事件730、TDL0包731，跨一拍；0°不接受previous[3]，confirm过滤。样本728实际是fall_slots=1000而非fall_previous。

候选E/F的功能输出测试：PASS，每方案3×1344脉冲，所有上升/下降配对、重复、孤立、错配、FIFO与宽度容差检查通过。原记录下降timestamp从19恢复20，重复上升从1降至0；这是重放结果，不是修复后上板实测。原多相确认帧仍存在，不声称严格onehot通过。

核心实现：FAIL，E新增12个负端点，最差-0.729ns；F新增14个负端点，最差-0.579ns。不能以ILA历史例外放行。SDF文件已生成，注释及后仿未执行。没有生成Baseline.bit或Corrected.bit。

最终保持A/Baseline，正式RTL五文件哈希不变，原生产与Debug BIT哈希不变；没有烧录。根本物理相位偏移来源仍不充分，270°编码前信号与模拟输入证据尚缺。详见README、真实CSV复现、方案比较和时序报告。
''',encoding='utf-8')
print('FINALIZED_STOP_NO_ACCEPTED_FIX; FORMAL_BASELINE_AND_BOTH_OLD_BITS_UNCHANGED')

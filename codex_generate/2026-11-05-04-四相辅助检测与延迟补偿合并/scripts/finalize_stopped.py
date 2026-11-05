"""核心STA失败后的交付：明确未执行项，不编造新版SDF/精度/恢复结论。"""
from pathlib import Path
from collections import Counter,defaultdict
import ast,csv,hashlib,json,math,shutil,statistics

ROOT=Path('W:/');OLD=Path('U:/');PREV=Path('X:/')
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def stats(v):
    v=list(v)
    return dict(n=len(v),rmse_ps=math.sqrt(statistics.mean(x*x for x in v)),bias_ps=statistics.mean(v),std_ps=statistics.pstdev(v),max_abs_ps=max(map(abs,v)))

def main():
    timing=json.loads((ROOT/'results/TIMING_REVIEW.json').read_text());assert not timing['main_static_pass']
    validation=json.loads((ROOT/'VALIDATION.json').read_text());assert not validation['bit_generation_allowed']
    assert not list((ROOT/'results/compensated').glob('*.bit')) and not (ROOT/'results/compensated/gate_full').exists()
    refs={'A_original_baseline':OLD/'results/original/baseline/gate_validation','B_previous_compensated':OLD/'results/optimized/compensated/gate_validation','A2_optimized_baseline':OLD/'results/optimized/baseline/gate_validation','D_aux4_baseline':PREV/'results/baseline/gate_full'}
    truthsha=sha(ROOT/'sim/stimuli/full_truth.csv');historical={};measures={};sources={}
    for name,source in refs.items():
        dest=ROOT/'results/historical'/name;dest.mkdir(parents=True,exist_ok=True)
        assert sha(source/'truth.csv')==truthsha
        for filename in ['summary.json','measurements.csv','associated_timestamps.csv','candidate.csv','raw.csv','timestamps.csv','widths.csv','fifo.csv','errors.csv','error_fifo.csv','clock_epoch.csv','run_manifest.txt']:
            shutil.copyfile(source/filename,dest/filename)
        historical[name]=json.loads((source/'summary.json').read_text())
        measures[name]={int(r['pulse_id']):r for r in read(source/'measurements.csv') if int(r['matched'])}
        sources[name]={'source':str(source),'truth_sha256':truthsha,'files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in dest.iterdir()}}
    (ROOT/'inputs/HISTORICAL_REFERENCE.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
    metrics=[]
    for name,s in historical.items():
        for metric,st in [('rise',s['rise']),('fall',s['fall'])]:
            metrics.append(dict(version=name,level='MAX_SDF_HISTORICAL',scope='available_edges',group='all',metric=metric,status='OBSERVED_HISTORICAL_FAILURE' if s['faults'] else 'OBSERVED',expected_pulses=3512,valid_matched_pulses=s['valid_matched_pulses'],valid_rate=s['valid_rate'],n=st['n'],rmse_ps=st['rmse_ps'],bias_ps=st['bias_ps'],std_ps=st['std_ps'],max_abs_ps=st['max_abs_ps'],reason='原失败样本保留，统计不代表3512完整验收通过'))
        for group,st in s['groups'].items():
            metrics.append(dict(version=name,level='MAX_SDF_HISTORICAL',scope='correctly_paired_only',group=group,metric='pulse_width',status='COMPLETE_GROUP' if st['complete'] else 'INCOMPLETE_GROUP',expected_pulses=3512,valid_matched_pulses=s['valid_matched_pulses'],valid_rate=s['valid_rate'],n=st['n'],rmse_ps=st['rmse_ps'],bias_ps=st['bias_ps'],std_ps=st['std_ps'],max_abs_ps=st['max_abs_ps'],reason='错误配对不纳入精度；原missing/faults清单完整保留'))
    common=set(measures['A_original_baseline'])&set(measures['B_previous_compensated'])
    for name in ['A_original_baseline','B_previous_compensated']:
        st=stats(float(measures[name][i]['error_ps']) for i in common)
        metrics.append(dict(version=name,level='MAX_SDF_HISTORICAL',scope='AB_same_event_ids',group='all',metric='pulse_width',status='COMMON_IDS_ONLY',expected_pulses=3512,valid_matched_pulses=historical[name]['valid_matched_pulses'],valid_rate=historical[name]['valid_rate'],**st,reason='固定相同事件ID，未删除离群样本'))
    for metric in ['rise','fall','pulse_width']:
        metrics.append(dict(version='C_aux4_compensated',level='MAX_SDF',scope='full_3512',group='all',metric=metric,status='NOT_EXECUTED',expected_pulses=3512,valid_matched_pulses='',valid_rate='',n='',rmse_ps='',bias_ps='',std_ps='',max_abs_ps='',reason='核心STA失败，按任务原则停止后续依赖步骤'))
    write(ROOT/'BASELINE_VS_COMPENSATED.csv',metrics)
    eventcomparison=[]
    for i in range(3512):
        row={'event_id':i,'AB_common_id':int(i in common)}
        for name in refs:
            m=measures[name].get(i);row[name+'_matched']=int(m is not None);row[name+'_width_error_ps']=m['error_ps'] if m else ''
        row['C_aux4_compensated_status']='NOT_EXECUTED';row['C_width_error_ps']='';eventcomparison.append(row)
    write(ROOT/'results/HISTORICAL_EVENT_COMPARISON.csv',eventcomparison)
    audit=read(ROOT/'results/RTL_COMPENSATION_TRACE.csv');params=read(ROOT/'inputs/frozen_compensation.csv');phase=[]
    for p in params:
        g=[r for r in audit if r['sel_index']==p['sel_index'] and r['polarity']==p['polarity']]
        phase.append(dict(tdl_phase=p['tdl_phase'],sel_index=p['sel_index'],polarity=p['polarity'],offset_ps=p['offset_ps'],offset_unit='ps',rtl_formula_checks=len(g),rtl_raw_fine_min_ps=min(int(r['raw_fine_ps']) for r in g),rtl_raw_fine_max_ps=max(int(r['raw_fine_ps']) for r in g),sdf_status='NOT_EXECUTED',sdf_sample_count='',raw_bias_ps='',compensated_bias_ps='',raw_relative_to_tdl0_ps='',compensated_relative_to_tdl0_ps='',reason='缺少本版SDF实际测量，不估算残余固定延迟'))
    write(ROOT/'PHASE_COMPENSATION_REPORT.csv',phase)
    associated=read(ROOT/'results/rtl/baseline/rtl_full/associated.csv');counts=Counter((int(r['pulse_id']),int(r['type'])) for r in associated)
    recovered=[]
    for i in [2917,2918,2983,2984,3049,3050]:
        assert counts[i,1]==counts[i,0]==1
        recovered.append(dict(event_id=i,rtl_rise_count=counts[i,1],rtl_fall_count=counts[i,0],rtl_correct_width_count=1,rtl_status='PASS',sdf_rise_count='',sdf_fall_count='',sdf_correct_width_count='',sdf_status='NOT_EXECUTED',reason='补偿RTL与旁路前端逐字节一致且全量补偿算术检查通过；不能代替新实现SDF'))
    write(ROOT/'EVENT_RECOVERY.csv',recovered)
    core=timing['negative_setup_core'];write(ROOT/'results/CORE_SETUP_VIOLATIONS.csv',core)
    boundary=read(ROOT/'results/compensated/module_all_boundary_setup.csv');module={}
    for r in boundary:module[r['module']]=min(module.get(r['module'],float('inf')),float(r['slack_ns']))
    modules='\n'.join(f"| {name} | {slack:+.3f} |" for name,slack in module.items())
    paths='\n'.join(f"- {r['slack_ns']} ns：`{r['startpoint']}` → `{r['endpoint']}`。" for r in core)
    (ROOT/'TIMING_REVIEW.md').write_text(f'''# 核心时序验收：FAIL

器件xc7k325tffg900-2，Vivado 2022.2，500MHz四相；Slow/MAX Setup、Fast/Min Hold；沿用原有效XDC和IP约束，没有新增false path或multicycle。

WNS {timing['wns_ns']:.3f}ns，TNS {timing['tns_ns']:.3f}ns；WHS {timing['whs_ns']:.3f}ns，THS {timing['ths_ns']:.3f}ns；18个Setup端点失败、0个Hold失败。
其中14个ILA2端点与历史辅助Baseline相同，逐个实际扇出检查不回馈测量/FIFO；4个核心端点不能归入ILA或TDL异步采样告警。

## 4条真实同步Setup违例

{paths}

Locate最差路径属于原第5级时间戳模归一化/选择：s4_sum低位 → LUT2 → 3个CARRY4 → wrapped_time2 → LUT5 → timestamp高位。该路径不位于TDL采样或辅助同步器中。
实际数据延迟1.971ns（逻辑0.771、布线1.200），2ns周期，clock skew -0.050ns、uncertainty0.060ns。wrapped_time2单段网线0.708ns、扇出21。
旧Compensated的Locate最差-0.019ns；新版本-0.047ns，恶化28ps；相对于四相辅助Baseline的+0.021ns，恶化68ps。
这说明原补偿路径仍未收敛，不是RTL算法或新辅助采样功能错误的证据；不能凭STA推断具体输入事件一定丢失或一定通过。

结果FIFO违例是rst_sync_500m_reg[1] → 两级LUT → BRAM ENARDEN，数据延迟1.613ns（逻辑0.370、布线1.243），skew -0.017ns；同步复位释放后的控制路径真实参与测量FIFO，不能当作异步TDL告警或随意false-path。
模块输出端统计会漏掉来自外部复位寄存器的路径，因此本报告取from/to两类路径较差值。

## 模块最差Setup（含输入边界）

| 模块 | 最差裕量ns |
|---|---:|
{modules}

辅助Setup +0.220ns、Hold +0.108ns，与6b341d8辅助Baseline相同。327个TDL/CARRY/thermo/分发树单元的类型、LOC、BEL全部相同。
check_timing：no_clock=0、unconstrained_internal_endpoints=0、loops=0；原两个no_input_delay仍为sys_rst_n/pwm_in，并非新增漏约束。未关闭timing check。
6748条可布线网络全部已布线，route错误0；没有构建ERROR或Critical Warning。工具将原Explore请求按增量参考覆盖为RuntimeOptimized，实际日志保留，未把请求指令当作实际指令。

## 停止点与后续建议

依据本次任务“如果任何一步失败，停止后续依赖步骤”，没有运行新Compensated完整MAX-SDF，没有进行SDF精度/残余延迟验收，没有生成最终BIT。
已导出网表和Slow SDF仅用于下一步定位，未编译/注释，不能标注为验证通过。
最小后续方向：先审查Locate模回卷比较/选择路径及FIFO复位控制的布局、扇出和布线；保留补偿公式、位宽、5级流水与有效时序。若需改变流水结构或FIFO/复位架构，应作为新任务先分析，不在本次合并中擅自修改。

证据：results/compensated/locate_setup_top100.rpt、reset_control_setup_top50.rpt、result_fifo_incoming_setup_top50.rpt、module_all_boundary_setup.csv、negative_setup_reachability.csv、timing_summary.rpt及只读failure_audit_timing_summary.rpt。
''',encoding='utf-8')
    table=[]
    for name,s in historical.items():
        st=s['groups']['all'];table.append(f"| {name} | {s['valid_matched_pulses']}/3512 | {st['rmse_ps']:.3f} | {st['bias_ps']:.3f} | {st['std_ps']:.3f} |")
    table.append('| C 新四相辅助+Compensated | 未执行 | — | — | — |')
    (ROOT/'RESULTS.md').write_text('''# 四相辅助检测与延迟补偿合并

**最终验收：FAIL。独立合并和全量RTL验证完成；实现后发现4条核心Setup违例，按任务要求停止后续依赖步骤，未运行新Compensated完整MAX-SDF，未生成最终BIT。**

## 1. 版本来源与修改范围

原Compensated：`d30dfeb9779f7d3c4859fbfb300bebd2d9481a7b`，`2026-11-05-01-四相TDC时序优化与连续测量验证/results/optimized/compensated/`。
四相辅助Baseline：`6b341d88497541f23eaefee1cfad4e4925c7f2aa`，`2026-11-05-03-四相TDC辅助边沿检测优化/rtl/`。
12个Git对象与本地源文件完成逐字节或仅CRLF等价校验，参数CSV哈希与原Compensated一致，见inputs/SOURCE_PROVENANCE.json。

本任务rtl/5个文件与6b341d8的辅助Baseline逐字节一致。相对于旧Compensated仅tdc_fine_layer.v变化：直接复用已通过的四相辅助采样、电平传输、有序边沿归属、rise/fall去重和confirm_edge；没有删寄存器、调整时序顺序或引入Toggle。
top、candidate、locate、merge逐字节保留旧补偿版本。实际启用补偿通过inputs/compensation_params.tcl的原generic与sim/compensation_parameters.vh完成，没有重写算法或改参数默认值。
正式工程当前Baseline与历史目录均未覆盖，5个正式RTL哈希不变；新增/修改的实验文件仅在本任务目录，另在任务索引追加一行。
四个版本源码分别保存在original/baseline_original、original/baseline_aux4、original/compensated_previous、rtl；历史大型实现文件保持原路径，不重复复制，源码/参数/测量证据有独立副本。

## 2. 补偿参数与原算法

| 物理TDL | 相位 | sel_index | Rise ps | Fall ps |
|---|---:|---:|---:|---:|
| TDL0 | 0°（下一周期） | 3 | 36081 | 36081 |
| TDL1 | 90° | 0 | 36011 | 36011 |
| TDL2 | 180° | 1 | 35742 | 35742 |
| TDL3 | 270° | 2 | 35756 | 35756 |

8参数来自旧独立SDF校准，包含公共流水线、输入分发及粗时间epoch的偏移，不能当作只有相对通道偏差。Rise/Fall独立选择，本组冻结值相等；没有全部设成相同值、没有重新拟合。
补偿位于候选选择后Time Locate中：第1级锁定code/index/type，第2级把原mid-offset常量与fine、coarse并行锁定，第3级计算relative，第4级加粗时间，第5级正常模回卷。
fine_rise=code×10ps；fine_fall=(64-code)×10ps；timestamp=(coarse×2000+mid-fine-offset) mod 2048000ps。正offset从正向时间戳减去。
保持18位有符号参数、19位中细时间、COARSE_W+11=21位输出、扩展有符号运算，10ps/tap；无新增舍入。原参数拟合的round规则未再执行。
脉宽修正关系为width_C=width_B+offset_rise-offset_fall（正常模回卷），公共偏移相消；该修正不改变输入真实PWM宽度，测量值会按原算法修正。

## 3. RTL功能验证：PASS

- 使用与6b341d8完全相同的3512脉冲输入/边沿/频率/占空比/扰动及真值文件，SHA256相同；没有减少或调整样本。
- 旁路与补偿各输出7024个边沿、3512个脉宽；前端raw/candidate/sampled_taps/aux_trace逐字节一致，FIFO序列等于脉宽输出，错误FIFO为空。
- 旁路的candidate/timestamps/widths/fifo与6b341d8冻结RTL结果逐字节相同；由此复用严格事件归属，补偿只改变原算术，7024次timestamp及3512次width逐项核对通过。
- valid、极性、候选选择、输出周期全部一致，未增加流水拍数。
- 8321个Locate边界样本覆盖4相×2极性×65有效tap的520组合，162次负向回卷、1次正向回卷，无无符号下溢或格式变化。
- 六个历史ID的rise/fall/width在RTL中各恢复一次。**新实现的SDF恢复情况未执行，不能沿用旧Baseline的SDF成功结论。**

观察数据：results/rtl/*/rtl_full中的raw/candidate/timestamps/widths/FIFO等CSV，results/RTL_COMPENSATION_TRACE.csv、LOCATE_BOUNDARY_INPUT/OUTPUT.csv及RTL_STAGE_GATE.json。
首轮统计错误使用SDF物理延迟关联理想RTL，导致假错配；已确认原CSV与旧RTL逐字节一致，修正为旧RTL专用关联方法，失败分析完整保存在analysis_failed_sdf_reference，未改原始仿真数据。
首次边界覆盖检查发现缺少正向回卷用例，保留原测试日志并补充该用例后通过；未修改正式RTL。

## 4. 实现后验证与停止原因

完成一次顶层综合与布局布线，IP配置保持原值，在新目录登记并生成OOC产品；复用6b341d8路由参考、原有效XDC和既有ILA布局/BRAM功耗脚本。
导出同一冻结设计的design.dcp、design.v、Slow design.sdf、完整报告；未生成BIT。

全局WNS=-0.050ns、TNS=-0.257ns、WHS=+0.054ns、THS=0；18个Setup失败端点中14个为历史ILA2，4个是真实核心路径。
Locate最差-0.047ns（旧Compensated -0.019ns、辅助Baseline +0.021ns），另外Locate -0.022/-0.002ns；结果FIFO输入复位控制到BRAM ENARDEN -0.018ns。
辅助Setup/Hold仍为+0.220/+0.108ns，327个固定TDL/分发单元的类型/LOC/BEL保持不变。
**没有通过新增false path、降低500MHz或更改补偿/流水掩盖违例。** 详细起点、终点、逻辑及布线见TIMING_REVIEW.md。

## 5. SDF与四相残余固定延迟：未执行

因核心STA失败，完整MAX-SDF未编译、未运行，SDF注释成功率、动态timing warning及新版3512脉冲恢复情况均未取得。
PHASE_COMPENSATION_REPORT.csv列出原8参数及RTL算术覆盖；新版SDF raw/comp bias、相对TDL0残余延迟等字段明确留空并标注NOT_EXECUTED。
不能用RTL理想模型、旧Baseline或旧Compensated的SDF替代新实现证据，不能宣称四相残余延迟改善。

## 6. 精度比较

以下历史版本使用同一3512真值，保留各版本失败事件；RMSE仅对正确配对子集统计，不把它当作全量通过。

| 版本 | 正确配对 | Width RMSE ps | Bias ps | STD ps |
|---|---:|---:|---:|---:|
'''+ '\n'.join(table)+'''

A为优化前原始Baseline；A2为Nov5时序优化Baseline；B为本次冻结参数对应的Nov5 Compensated；D为已验证的四相辅助Baseline，单独列出避免“Baseline”混淆。历史FAIL结论保持不变。
BASELINE_VS_COMPENSATED.csv保留历史Rise/Fall/Width RMSE、Bias/STD/MaxAbs及10MHz、20MHz、各占空比、ATC帧头/数据区统计，并列出A/B相同事件ID的公平比较。
逐事件误差保留在results/HISTORICAL_EVENT_COMPARISON.csv；源CSV和SHA256见results/historical及inputs/HISTORICAL_REFERENCE.json。
新版C的全部物理精度数据未执行，不能判断B/C同ID误差变化、频率切换影响或补偿效果是否保持；相应字段留空，而非填0或套用D的结果。
没有对3512验证数据重新拟合8参数，也没有删除离群样本。

## 7. BIT、限制与后续

最终Compensated BIT **未生成**。VALIDATION.json记录FAIL及bit_generation_allowed=false，完整SDF/物理补偿项目为NOT_EXECUTED_BLOCKED_BY_CORE_TIMING。
未执行硬件、其他PVT、2ns以下脉宽保证；旧版本的失败和先前bitstream保持原样。
下一步应先解决Locate最终模回卷路径及结果FIFO同步复位控制的实际Setup负裕量，再按完全相同3512激励运行完整MAX-SDF，验证四相残余延迟和B/C同ID精度，最后决定是否生成BIT。
本任务未做进一步时序优化或修改FIFO/流水，也未推送到GitHub；交付保存在本地独立任务目录。

文件清单见FILE_LIST.md，重要证据SHA256见SHA256SUMS.txt；复现及当前停止门槛见REPRODUCE.md。
''',encoding='utf-8')
    (ROOT/'REPRODUCE.md').write_text('''# 复现与当前停止门槛

所有运行应在新的工作副本中，禁止覆盖此处冻结CSV、日志和实现文件。正式Baseline不修改。
Windows短路径映射：W:=本任务副本；X:=2026-11-05-03辅助任务；U:=2026-11-05-01时序优化任务；V:=2026-11-05-02定位任务。
工具：F:/Program Files/Python313/python.exe；F:/iverilog/bin；F:/Xilinx/Vivado/2022.2/bin。Vivado的实际工作目录使用W:/logs，避免中文路径工具缺陷。

1. rtl/5个文件是已冻结合并结果，inputs/compensation_params.tcl及sim/compensation_parameters.vh保存原参数，勿重新运行校准脚本。
2. 在空结果目录运行scripts/run_rtl.py，得到全3512旁路/补偿数据及8321个Locate边界检查。
3. 运行prepare_build.py、Vivado register_ip.tcl、build_compensated.tcl，只导出路由结果不写BIT。
4. 只读运行audit_failure.tcl，再运行review_implementation.py（同时检查模块from/to输入边界）。
5. 当前核心STA失败，按任务约定到此停止。final_validation.py写FAIL并禁止BIT；finalize_stopped.py生成当前停止报告。

scripts/prepare_gate.py、run_gate.py、analyze_gate.py、compare_results.py保留后续验证入口，但本次未执行其SDF动作，不能视为已经验证过的新SDF观察映射。run_gate.py full要求main_static_pass=true。
未来修复应作为新的独立任务保存新实现，不覆盖此次失败证据；通过STA后再prepare/compile/full，完整仿真保持时序检查启用。full stimulus和truth均来自6b341d8，SHA已冻结。
final_validation.py只有RTL、核心STA、完整SDF、原参数算术/残余偏差及数据格式全部通过，才调用单独BIT脚本。当前不会调用。

本任务只有RTL功能仿真和实际综合实现/只读STA审查已经运行。MATLAB/硬件/新补偿校准均未执行。
''',encoding='utf-8')
    # 重要证据不含缓存和重复中间DCP；源文件、报告和原始CSV均参与SHA清单。
    files=[]
    for p in ROOT.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(ROOT)
        if any(part in ['build','__pycache__','.Xil','.cache'] for part in rel.parts) or p.name in ['SHA256SUMS.txt','FILE_LIST.md']:continue
        if p.suffix=='.dcp' and p.name!='design.dcp':continue
        files.append(p)
    files.sort(key=lambda p:p.relative_to(ROOT).as_posix())
    (ROOT/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in files),encoding='utf-8')
    (ROOT/'FILE_LIST.md').write_text('# 交付文件清单\n\n不列缓存、IP生成产品和重复中间DCP；它们仍保留在本地build及实现目录。下列为关键源码、配置、原始CSV、报告、完整工具日志及最终失败实现证据。\n\n| 文件 | 字节 |\n|---|---:|\n'+''.join(f'| {p.relative_to(ROOT).as_posix()} | {p.stat().st_size} |\n' for p in files),encoding='utf-8')
    for p in (ROOT/'scripts').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
    print('STOPPED_DELIVERY_READY',len(files),'important files; core violations',len(core),'BIT not generated')
    print('HISTORICAL_METRICS',json.dumps({n:s['groups']['all'] for n,s in historical.items()},ensure_ascii=False))

if __name__=='__main__':main()

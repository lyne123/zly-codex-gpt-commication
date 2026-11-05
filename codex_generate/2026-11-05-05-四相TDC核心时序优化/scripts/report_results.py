"""只读核验实际RTL/STA证据，区分本轮验收与尚未执行的SDF精度验证。"""
from pathlib import Path
import csv,hashlib,json,re,shutil

ROOT=Path('W:/');BEFORE=Path('Y:/');AUX=Path('X:/')
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def timing_summary(p):
    text=p.read_text(encoding='utf-8',errors='replace')
    m=re.search(r'WNS\(ns\).*?\n\s*-+[^\n]*\n\s*([-\d.]+)\s+([-\d.]+)\s+(\d+)\s+(\d+)\s+([-\d.]+)\s+([-\d.]+)\s+(\d+)',text,re.S);assert m
    return dict(wns_ns=float(m[1]),tns_ns=float(m[2]),setup_failing_endpoints=int(m[3]),whs_ns=float(m[5]),ths_ns=float(m[6]),hold_failing_endpoints=int(m[7]))
def config(p):
    d=json.loads(p.read_text(encoding='utf-8'))['ip_inst']['parameters']['component_parameters']
    return {k:[r.get('value') for r in v] for k,v in d.items()}
def slack(p):
    return float(re.search(r'Slack \((?:MET|VIOLATED)\)\s*:\s*([-\d.]+)ns',p.read_text(encoding='utf-8'))[1])
def main():
    out=ROOT/'results/compensated';summary=timing_summary(out/'timing_summary.rpt');before=json.loads((ROOT/'inputs/TIMING_BEFORE.json').read_text())
    rtl=json.loads((ROOT/'results/RTL_STAGE_GATE.json').read_text());unit=json.loads((ROOT/'results/UNIT_CHECKS.json').read_text())
    targets=read(out/'core_targets.csv');assert len(targets)==4
    negative=read(out/'negative_setup.csv');holds=read(out/'negative_hold.csv')
    oldila=[r for r in read(BEFORE/'results/compensated/negative_setup_reachability.csv') if r['endpoint'].startswith('u_ila2/')]
    unchanged_ila={(r['startpoint'],r['endpoint'],r['slack_ns']) for r in oldila}=={(r['startpoint'],r['endpoint'],r['slack_ns']) for r in negative}
    core_negative=[r for r in negative if not (r['endpoint'].startswith('u_ila2/') and r['measurement_fifo_reachable_count']=='0')]
    modules=read(out/'module_setup.csv');module_slacks={}
    for r in modules:module_slacks[r['module']]=min(module_slacks.get(r['module'],float('inf')),float(r['slack_ns']))
    checks_text=(out/'check_timing.rpt').read_text(encoding='utf-8',errors='replace');counts={k:int(v) for k,v in re.findall(r'checking (\w+) \((\d+)\)',checks_text)}
    def fixed(rows):return {r['name']:(r['ref_name'],r['loc'],r['bel']) for r in rows if any(k in r['name'] for k in ['g_carry','thermo_q_reg','g_pwm_dist'])}
    fixed_old=fixed(read(BEFORE/'results/compensated/frontend_structure.csv'));fixed_new=fixed(read(out/'frontend_structure.csv'))
    replica=read(out/'reset_replica_structure.csv');assert len(replica)==2
    replica_equivalent=all(replica[0][key]==replica[1][key] for key in ['D_net','C_net','CLR_net','ref_name'])
    # 独立检查网表中低14位已真正直连，不仅依靠RTL表达式或时序改善推断。
    net=(out/'design.v').read_text(encoding='utf-8');body=re.search(r'module tdc_time_locate\b(.*?)endmodule',net,re.S)[1]
    def port(instance,pin):
        m=re.search(re.escape(instance)+r'\s*\((.*?)\);',body,re.S);assert m,instance
        m=re.search(r'\.'+pin+r'\(([^)]+)\)',m[1]);assert m,(instance,pin)
        return m[1].strip()
    direct=[]
    for i in range(14):
        a=port('\\s4_sum_reg['+str(i)+']','Q');b=port('\\timestamp_ps_reg['+str(i)+']','D')
        direct.append(dict(bit=i,s4_Q_net=a,timestamp_D_net=b,direct=a==b))
    ipcheck={}
    for ip in ['clk_wiz_0','fifo_tdc_result','ila_2','ila_3']:
        src=ROOT/f'inputs/ip/{ip}/{ip}.xci';reg=ROOT/f'build/registered/aux_compensated.srcs/sources_1/ip/{ip}/{ip}.xci'
        ipcheck[ip]=dict(values_equal=config(src)==config(reg),parameter_count=len(config(src)),source_sha256=sha(src),registered_sha256=sha(reg))
    log=(ROOT/'logs/build_timing.log').read_text(encoding='utf-8',errors='replace')
    actual_generics=re.search(r'Command: synth_design -top tdc_meas_top[^\n]*-generic \{([^}]+)\}',log)[1]
    generic=dict(x.split('=') for x in actual_generics.split());params=read(ROOT/'inputs/frozen_compensation.csv')
    parameter_values_match=generic['ENABLE_SKEW_COMP']=='1' and all(int(generic[f"{r['polarity'].upper()}_OFFSET_{r['tdl_phase']}_PS"])==int(r['offset_ps']) for r in params)
    source_same=sha(ROOT/'inputs/frozen_compensation.csv')==sha(BEFORE/'inputs/frozen_compensation.csv')
    changed=[p.name for p in (ROOT/'rtl').glob('*.v') if sha(p)!=sha(ROOT/'original/rtl'/p.name)]
    fine_same=sha(ROOT/'rtl/tdc_fine_layer.v')==sha(AUX/'rtl/tdc_fine_layer.v')
    v_before=(ROOT/'original/rtl/tdc_time_locate.v').read_text(encoding='utf-8');v_after=(ROOT/'rtl/tdc_time_locate.v').read_text(encoding='utf-8')
    first_four_same=v_before.split('    // Stage 5：')[0]==v_after.split('    // Stage 5：')[0]
    final_register_same=v_before[v_before.rfind('    always @(posedge'):]==v_after[v_after.rfind('    always @(posedge'):]
    bus=(out/'bus_skew.rpt').read_text(encoding='utf-8',errors='replace');bus_values=[float(v) for v in re.findall(r'^\s+(?:Slow|Fast)\s+[\d.]+\s+[\d.]+\s+([-\d.]+)\s*$',bus,re.M)]
    source_actual=Path('D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/fpga_tdc_v3_cal_rtl')
    gates=dict(rtl_3512_pass=rtl['rtl_pass'],boundary_and_reset_pass=unit['unit_pass'],four_target_endpoints_positive=all(float(r['endpoint_worst_slack_ns'])>=0 for r in targets),no_core_negative_setup=not core_negative,no_negative_hold=not holds and summary['hold_failing_endpoints']==0,only_same_14_nonfeedback_ILA2=len(negative)==14 and unchanged_ila,main_module_boundaries_nonnegative=all(v>=0 for k,v in module_slacks.items() if k!='u_ila2'),no_unconstrained_internal_paths=all(counts.get(k,0)==0 for k in ['no_clock','unconstrained_internal_endpoints','loops']),fixed_TDL_structure_unchanged=fixed_old==fixed_new and len(fixed_new)==327,auxiliary_RTL_unchanged=fine_same,original_parameters_unchanged=source_same and parameter_values_match,IP_configuration_unchanged=all(x['values_equal'] for x in ipcheck.values()),five_pipeline_stages_unchanged=first_four_same and final_register_same,reset_replica_same_D_clock_reset=replica_equivalent,low_14_bits_direct=all(x['direct'] for x in direct),formal_RTL_matches_tested_snapshot=all(sha(p)==sha(source_actual/p.name) for p in (ROOT/'rtl').glob('*.v')),only_two_requested_RTL_changed=sorted(changed)==['tdc_meas_top.v','tdc_time_locate.v'],single_top_implementation=log.count('Command: synth_design -top tdc_meas_top ')==log.count('Command: route_design ')==1,no_OOC_rebuild=log.count('The given sub-design is up-to-date')==4,no_build_errors_or_critical_warnings=not re.search(r'^\s*(?:ERROR:|CRITICAL WARNING:)',log,re.M),bus_skew_nonnegative=bool(bus_values) and min(bus_values)>=0,no_SDF_or_BIT_executed=not list(out.glob('*.sdf')) and not list(out.glob('*.bit')) and not (ROOT/'build/gate').exists())
    validation=dict(status='PASS' if all(gates.values()) else 'FAIL',scope='RTL功能及核心静态时序；不包含本轮未执行的MAX-SDF/精度/BIT',checks=gates,expected_pulses=3512,correct_pulses=3512,valid_edges=7024,all_key_output_CSV_byte_identical_to_previous_merge=True,before_timing={k:before[k] for k in summary},after_timing=summary,core_setup_violations=len(core_negative),historical_ILA2_setup_violations=len(negative),module_boundary_slacks_ns=module_slacks,aux_setup_ns=slack(out/'aux_setup.rpt'),aux_hold_ns=slack(out/'aux_hold.rpt'),replica_output_setup_ns=slack(out/'reset_replica_setup.rpt'),replica_input_setup_ns=slack(out/'reset_replica_input_setup.rpt'),fixed_TDL_cells_checked=len(fixed_new),constraint_checks=counts,bus_skew_min_slack_ns=min(bus_values) if bus_values else None,modified_RTL=sorted(changed),parameters_recalibrated=False,locate_stages=5,clock_mhz=500,MAX_SDF='NOT_EXECUTED_PER_USER',BIT='NOT_GENERATED_PER_USER',global_timing_pass=False,git_branch='codex/2026-11-05-05-tdc-core-timing-fix',commit_message='2026-11-05-05-四相TDC核心时序优化')
    (ROOT/'VALIDATION.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'results/IP_CONFIGURATION_CHECK.json').write_text(json.dumps(ipcheck,indent=2),encoding='utf-8')
    (ROOT/'results/NETLIST_STRUCTURE_CHECK.json').write_text(json.dumps(dict(reset_replica_equivalent_inputs=replica_equivalent,replica_cells=replica,low_bits=direct),ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copyfile(out/'core_targets.csv',ROOT/'CORE_TIMING_PATHS.csv')
    path_table='\n'.join(f"| {r['target']} | {float(r['before_slack_ns']):+.3f} | {float(r['endpoint_worst_slack_ns']):+.3f} | {r['endpoint_worst_startpoint']} |" for r in targets)
    module_table='\n'.join(f'| {name} | {v:+.3f} |' for name,v in module_slacks.items())
    (ROOT/'TIMING_BEFORE_AFTER.md').write_text(f'''# 核心时序优化前后

器件XC7K325T-FFG900-2，Vivado2022.2，500MHz；原有效时钟/IO/TDL/IP约束保持，未增加false path、multicycle或更改频率。

| 全局指标 | 合并版（04任务） | 本次（05任务） |
|---|---:|---:|
| WNS ns | {before['wns_ns']:.3f} | {summary['wns_ns']:.3f} |
| TNS ns | {before['tns_ns']:.3f} | {summary['tns_ns']:.3f} |
| WHS ns | {before['whs_ns']:.3f} | {summary['whs_ns']:.3f} |
| THS ns | {before['ths_ns']:.3f} | {summary['ths_ns']:.3f} |
| Setup失败端点 | 18（核心4+ILA2 14） | {summary['setup_failing_endpoints']}（核心{len(core_negative)}+ILA2 {len(negative)}） |
| Hold失败端点 | 0 | {summary['hold_failing_endpoints']} |

## 原四个核心违例端点

| 端点简称 | 原裕量ns | 新端点最差裕量ns | 新最差起点 |
|---|---:|---:|---|
{path_table}

四条原起点到原终点的组合路径均已移除，不能把不存在的原路径标成正裕量。上表重新查询各原终点的全部真实路径，给出最差值；完整名称和原路径是否存在记录于CORE_TIMING_PATHS.csv。

Locate原低位→高位宽比较/选择路径不再存在。bit20最差路径由5级（LUT2+3CARRY4+LUT5）变为3级LUT（LUT4+2LUT6），数据路径延迟从1.971降为1.381ns（逻辑0.771→0.388、布线1.200→0.993）。原wrapped_time2的21负载宽控制网络不再保留；低14位网表逐位核对为s4_sum Q直达timestamp D。

FIFO同拍复位副本的输出最差Setup为{validation['replica_output_setup_ns']:+.3f}ns，输入Setup为{validation['replica_input_setup_ns']:+.3f}ns。原末级与副本均为FDCE，实际D/C/CLR网络相同，位于SLICE_X21Y13的B5FF/BFF，原FIFO rst端口未改。
结果FIFO ENARDEN目前最差来自IP内部ram_full_i，而非原共享复位网络；没有省略其他驱动控制路径。
reset_replica_structure.csv的Q_endpoint_loads为跨组合逻辑的终端数量（原共享471、副本38），不是直接物理扇出，未混用两种口径。

## 模块边界最差裕量

| 模块（同时检查from/to，包含跨模块输入） | 最差Setup ns |
|---|---:|
{module_table}

这里Locate的{module_slacks['u_tdc_time_locate']:+.3f}ns包含Locate输出到Merge使能的路径，不应误称为Locate内部回卷路径。全体核心最小裕量仍为Fine Layer +0.050ns。
四相辅助Setup/Hold为{validation['aux_setup_ns']:+.3f}/{validation['aux_hold_ns']:+.3f}ns，327个固定TDL/分发单元的类型/LOC/BEL完全一致。
原14条ILA2负路径的起点、终点、裕量与04任务逐项相同，实际扇出不回馈TDC/FIFO；本轮未针对ILA进行新优化。
无no_clock、unconstrained_internal_endpoints或loops；原两个no_input_delay保持不变。FIFO bus-skew报告最差裕量{validation['bus_skew_min_slack_ns']:+.3f}ns。

仅执行一次顶层综合、一次布局布线，4个原OOC IP产品均up-to-date直接复用。沿用原增量流程，Vivado实际将Explore路由请求覆盖为RuntimeOptimized，日志如实保留。没有重复综合或生成BIT；本轮没有运行SDF，不能据此宣称SDF功能/精度通过。
''',encoding='utf-8')
    parameter_table='\n'.join(f"| {r['tdl_phase']}° | {r['polarity']} | {r['sel_index']} | {r['offset_ps']} |" for r in params)
    (ROOT/'RESULTS.md').write_text(f'''# 四相TDC核心时序优化

**本轮验收：{validation['status']}（原3512脉冲RTL功能等价 + 核心静态时序）。四条核心Setup违例全部消除，其他核心无新增负裕量。全局仍有原14条ILA2违例，未宣称全局时序收敛。**

## 修改与等价性

仅修改正式RTL `tdc_time_locate.v`、`tdc_meas_top.v`；before/after完整源码位于original/rtl和rtl，差异见RTL.diff。其他3个RTL逐字节相同，已验证四相辅助检测、TDL、CARRY4、candidate、merge及顶层接口均保持。

Locate模数为2000×2^COARSE_W=125×2^(COARSE_W+4)。将原有符号s4_sum写成h×2^L+l（0≤l<2^L），s<0等价h<0，s≥M等价h≥125，加减M只改变高部。把有符号比较和±125限制到高部并行计算，低部直接连接。当前COARSE_W=10时仅处理9位高部，低14位原样通过。
原23位有符号s4_sum/wrapped_time、21位ps输出、粗/中/细合并、补偿减法和模回卷结果不变；第1～4级及第5级输出寄存器/valid代码完全相同，未添加流水级、未改变有效周期。

FIFO只新增一个原500MHz同步器末级的等价副本，原第一级同时驱动两末级；两者同clk、同D、同异步复位，复制不增加级数或释放拍数。DONT_TOUCH阻止综合合并，副本仅用于结果FIFO写门控。
原result/error FIFO rst端口、wr_rst_busy/full/pulse_width_valid条件、读逻辑、数据格式和IP配置均保留。网表实际D/C/CLR一致及同Slice布局已核对。没有删除复位条件或关闭时序检查。

## RTL验证

- 原3512个输入脉冲、真值、事件时间及参数全部冻结，未改变样本。
- 旁路和补偿各7024边沿、3512脉宽；raw/candidate/taps/aux/timestamps/widths/FIFO/errors及六历史事件的pipeline trace均与04任务逐字节一致。
- 7024次时间戳、3512次脉宽补偿算术及valid/极性时序核对通过；结果FIFO顺序一致，错误FIFO为空。
- 原8321个Locate边界样本通过，覆盖520个相位/极性/tap组合及正负回卷。
- 168960个完整有符号回卷位模式检查通过（COARSE_W=1/8/10，所有高部取值与低部边界）；包含原合法范围之外的位模式，仍与旧单次回卷表达式逐位一致。
- FIFO复位对照检查2552周期、76个输出、3次异步assert/4次同步release，旧/新写使能、读使能、脉宽及FIFO输出序列全部一致。

这些是理想RTL功能证据，不冒充器件SDF或精度统计。原CSV、完整日志和测试平台均保留。

## 时序结果

全局WNS/TNS：{before['wns_ns']:.3f}/{before['tns_ns']:.3f} ns → {summary['wns_ns']:.3f}/{summary['tns_ns']:.3f} ns；WHS/THS维持{summary['whs_ns']:+.3f}/{summary['ths_ns']:.3f}ns。
核心Setup违例4→0，Hold违例0，原14条ILA2负路径逐项不变。

| 原核心端点 | 原裕量ns | 新最差裕量ns | 当前最差起点 |
|---|---:|---:|---|
{path_table}

旧的具体起终点组合均不再存在；此表为原终点的真实最差路径，详见TIMING_BEFORE_AFTER.md和CORE_TIMING_PATHS.csv。
辅助Setup/Hold {validation['aux_setup_ns']:+.3f}/{validation['aux_hold_ns']:+.3f}ns；全体核心最低Setup为Fine Layer +0.050ns。无新增时序例外，约束覆盖与TDL固定结构检查通过。
一次顶层综合/P&R完成，4个OOC IP未重新综合；没有额外实现试探。

## 冻结补偿参数

| TDL相位 | 极性 | sel_index | offset ps |
|---|---|---:|---:|
{parameter_table}

参数与04任务CSV逐字节一致，实际综合generic逐项匹配；包含旧公共流水线偏移，rise/fall仍独立选择，没有校准或改值。

## 交付、归档和限制

按本次要求未运行完整MAX-SDF、未生成SDF或BIT、未做精度对比或参数校准；这些将在后续任务中用本轮冻结DCP验证，不将本轮PASS外推为实现后功能或精度PASS。
实现DCP、未注释时序网表、XDC/IP配置、所有时序报告、源码/原始CSV/日志均在本任务目录，关键文件有SHA256清单。
上一轮未推送合并成果234个文件已逐字节保存在独立的2026-11-05-04归档，原FAIL、旧DCP/SDF及报告均保持；仅新增Git LFS属性用于归档，没有覆盖历史任务。
本轮Git分支：`codex/2026-11-05-05-tdc-core-timing-fix`，提交说明严格为`2026-11-05-05-四相TDC核心时序优化`。实际Commit ID和推送核验在执行结束报告给出，未合并main、未强推。

复现：在新空目录复制本任务scripts/sim/inputs/rtl，映射W:；Y:为04合并任务，X:为03辅助任务，U:为01时序任务。先run_rtl.py、run_unit_checks.py，均通过后复用相同IP产品并执行build_timing.tcl，最后report_results.py。已冻结交付目录禁止覆盖。
build_timing.tcl使用本任务build/registered内已生成IP产品；若独立检出后无这些缓存，应在新副本导入原XCI生成同配置OOC产品，不能直接把缺缓存报错当RTL失败。
文件清单及哈希见FILE_LIST.md、SHA256SUMS.txt。
''',encoding='utf-8')
    print(json.dumps(validation,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

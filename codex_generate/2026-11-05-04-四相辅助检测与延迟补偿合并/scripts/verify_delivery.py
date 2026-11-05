"""核验来源、实际generic、IP配置、原始数据及失败停止点。"""
from pathlib import Path
import ast,csv,hashlib,json,re,shutil,subprocess,sys

ROOT=Path('W:/');PREV=Path('X:/');OLD=Path('U:/')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    if '--sha-only' in sys.argv:
        lines=(ROOT/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
        for line in lines:
            digest,name=line.split('  ',1);assert sha(ROOT/name)==digest,name
        print('SHA256_ALL_PASS',len(lines));return
    validation=json.loads((ROOT/'VALIDATION.json').read_text());assert validation['status']=='FAIL' and validation['formal_baseline_unchanged'] and not validation['bit_generation_allowed']
    assert validation['stage_status']['full_MAX_SDF']=='NOT_EXECUTED_BLOCKED_BY_CORE_TIMING'
    assert not (ROOT/'results/compensated/gate_full').exists() and not list((ROOT/'results/compensated').glob('*.bit'))
    assert sha(ROOT/'inputs/frozen_compensation.csv')==sha(OLD/'results/tdc_skew_calibration.csv')
    params=read(ROOT/'inputs/frozen_compensation.csv');assert len(params)==8
    log=(ROOT/'logs/build_compensated.log').read_text(encoding='utf-8',errors='replace')
    generic=re.search(r'Command: synth_design -top tdc_meas_top[^\n]*-generic \{([^}]+)\}',log)[1]
    values=dict(item.split('=') for item in generic.split());assert values['ENABLE_SKEW_COMP']=='1'
    for r in params:assert int(values[f"{r['polarity'].upper()}_OFFSET_{r['tdl_phase']}_PS"])==int(r['offset_ps'])
    ipcheck={}
    for ip in ['clk_wiz_0','fifo_tdc_result','ila_2','ila_3']:
        src=ROOT/f'inputs/ip/{ip}/{ip}.xci';registered=ROOT/f'build/registered/aux_compensated.srcs/sources_1/ip/{ip}/{ip}.xci'
        def component_values(p):
            d=json.loads(p.read_text(encoding='utf-8'))['ip_inst']['parameters']['component_parameters']
            return {k:[item.get('value') for item in v] for k,v in d.items()}
        a,b=component_values(src),component_values(registered);assert a==b,ip
        ipcheck[ip]=dict(parameter_values_equal=True,parameter_count=len(a),source_sha256=sha(src),registered_sha256=sha(registered))
    (ROOT/'results/IP_CONFIGURATION_CHECK.json').write_text(json.dumps(ipcheck,indent=2),encoding='utf-8')
    b=ROOT/'results/rtl/baseline/rtl_full';c=ROOT/'results/rtl/compensated/rtl_full'
    for name in ['raw.csv','candidate.csv','sampled_taps.csv','aux_trace.csv']:assert sha(b/name)==sha(c/name)
    for name in ['candidate.csv','timestamps.csv','widths.csv','fifo.csv']:assert sha(b/name)==sha(PREV/'results/rtl_a1_l0_d0_full_r4'/name)
    assert len(read(c/'timestamps.csv'))==7024 and len(read(c/'widths.csv'))==3512
    for name in ['errors.csv','error_fifo.csv']:assert not read(c/name)
    timing=json.loads((ROOT/'results/TIMING_REVIEW.json').read_text());assert len(timing['negative_setup_core'])==4 and timing['negative_setup_ila2_count']==14
    assert sum(r['endpoint'].startswith('u_tdc_time_locate/') for r in timing['negative_setup_core'])==3
    assert sum(r['endpoint'].startswith('u_fifo_tdc_result/') for r in timing['negative_setup_core'])==1
    for p in (ROOT/'scripts').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
    for name in ['RTL.diff','RESULTS.md','TIMING_REVIEW.md','VALIDATION.json','BASELINE_VS_COMPENSATED.csv','PHASE_COMPENSATION_REPORT.csv','EVENT_RECOVERY.csv']:assert (ROOT/name).exists(),name
    for name in ['design.dcp','design.v','design.sdf']:
        p=ROOT/'results/compensated'/name;assert p.stat().st_size>1000000
    formal=Path('D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/fpga_tdc_v3_cal_rtl')
    for p in (ROOT/'rtl').glob('*.v'):assert sha(p)==sha(PREV/'rtl'/p.name)==sha(formal/p.name)
    gitstatus=subprocess.check_output(['git','-C',str(PREV/'github'),'status','--porcelain'],text=True);assert not gitstatus
    configurations={
        'baseline_original':dict(source_archive_commit='d30dfeb9779f7d3c4859fbfb300bebd2d9481a7b',source_archive_path='original/rtl',ENABLE_SKEW_COMP=0,auxiliary='legacy single-phase',implementation_reference='U:/results/original/baseline'),
        'baseline_aux4':dict(source_commit='6b341d88497541f23eaefee1cfad4e4925c7f2aa',ENABLE_SKEW_COMP=0,ENABLE_AUX_4PHASE=1,implementation_reference='X:/results/baseline'),
        'compensated_previous':dict(source_commit='d30dfeb9779f7d3c4859fbfb300bebd2d9481a7b',ENABLE_SKEW_COMP=1,auxiliary='legacy single-phase',parameters_file='compensation_params.tcl',implementation_reference='U:/results/optimized/compensated')}
    for name,config in configurations.items():
        (ROOT/'original'/name/'VERSION.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copyfile(ROOT/'inputs/compensation_params.tcl',ROOT/'original/compensated_previous/compensation_params.tcl')
    mapping=[]
    for name in ['associated_timestamps.csv','channel_statistics.csv']:
        p=b/'analysis_failed_sdf_reference'/('original_'+name)
        mapping.append(dict(old_path=str(b/name),new_path=str(p),sha256=sha(p),reason='首轮错误分析产物移入失败记录，保留内容，避免混入最终RTL数据'))
    (ROOT/'inputs/FAILED_ANALYSIS_PATH_MAPPING.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
    result=dict(delivery_integrity_pass=True,experiment_acceptance='FAIL',actual_compensation_generics=values,IP_parameter_values_unchanged=True,formal_baseline_unchanged=True,verified_aux_source_byte_identical=True,old_parameters_byte_identical=True,raw_rtl_frontend_byte_identical=True,full_rtl_edges=7024,full_rtl_widths=3512,core_setup_violations=4,ILA2_setup_violations=14,full_MAX_SDF='NOT_EXECUTED',BIT='NOT_GENERATED',historical_git_worktree_clean=True,pushed_to_GitHub=False)
    (ROOT/'results/DELIVERY_VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

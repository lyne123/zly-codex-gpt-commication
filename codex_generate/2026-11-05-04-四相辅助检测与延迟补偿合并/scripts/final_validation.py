"""最终验收及BIT门槛；失败时保留所有证据并禁止生成BIT。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,subprocess

ROOT=Path('W:/');PREV=Path('X:/');OLD=Path('U:/')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    rtl=json.loads((ROOT/'results/RTL_STAGE_GATE.json').read_text())
    timing=json.loads((ROOT/'results/TIMING_REVIEW.json').read_text())
    gatepath=ROOT/'results/compensated/gate_full/VALIDATION.json'
    gate=json.loads(gatepath.read_text()) if gatepath.exists() else None
    comparepath=ROOT/'results/COMPARISON_VALIDATION.json'
    comparison=json.loads(comparepath.read_text()) if comparepath.exists() else None
    unchanged=all(sha(p)==sha(PREV/'rtl'/p.name) for p in (ROOT/'rtl').glob('*.v'))
    parameters=sha(ROOT/'inputs/frozen_compensation.csv')==sha(OLD/'results/tdc_skew_calibration.csv')
    truth=sha(ROOT/'sim/stimuli/full.txt')==sha(PREV/'results/baseline/gate_full/stimulus.txt') and sha(ROOT/'sim/stimuli/full_truth.csv')==sha(PREV/'results/baseline/gate_full/truth.csv')
    comp=(comparison['sdf_arithmetic_checks']==7024 and comparison['phase_bias_improved'] and comparison['recovered_events']) if comparison else None
    full=(gate['functional_pass'] and gate['annotation_success'] and gate['active_synchronous_warning_count']==0 and gate['correct_widths']==3512 and gate['actual_edges']==7024) if gate else None
    checks=dict(rtl_functional=rtl['rtl_pass'],verified_aux_rtl_unchanged=unchanged,original_parameters_unchanged=parameters,identical_full_stimulus_and_truth=truth,full_MAX_SDF=full,phase_compensation=comp,core_static_timing=timing['main_static_pass'],format_and_valid_timing=rtl['timestamp_checks']==7024 and rtl['width_checks']==3512)
    result=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,bit_generation_allowed=all(checks.values()),global_timing_pass=timing['wns_ns']>=0 and timing['whs_ns']>=0,global_ILA2_violations_separate=True,rtl_source_commit='6b341d88497541f23eaefee1cfad4e4925c7f2aa',previous_compensated_commit='d30dfeb9779f7d3c4859fbfb300bebd2d9481a7b',validation_time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),bit_generated=False)
    result['stage_status']={'source_and_merge':'PASS','rtl_functional':'PASS' if rtl['rtl_pass'] else 'FAIL','synthesis_and_route':'COMPLETED','core_static_timing':'PASS' if timing['main_static_pass'] else 'FAIL','full_MAX_SDF':'PASS' if full else 'FAIL' if gate else 'NOT_EXECUTED_BLOCKED_BY_CORE_TIMING','physical_compensation_and_C_precision':'PASS' if comp else 'FAIL' if comparison else 'NOT_EXECUTED_BLOCKED_BY_CORE_TIMING','final_BIT':'NOT_GENERATED'}
    result['core_setup_violation_count']=len(timing.get('negative_setup_core',[]))
    formal=Path('D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/fpga_tdc_v3_cal_rtl')
    result['formal_baseline_unchanged']=all(sha(p)==sha(formal/p.name) for p in (ROOT/'rtl').glob('*.v'))
    (ROOT/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['bit_generation_allowed']:return
    dcp=ROOT/'results/compensated/design.dcp';out=ROOT/'results/compensated/Compensated_Aux4Phase.bit'
    if out.exists():raise RuntimeError('禁止覆盖已生成BIT')
    # 原路由检查点只读打开后直接写BIT，不改变设计、时序例外或布局布线。
    script=ROOT/'scripts/generate_bit.tcl'
    script.write_text('set_param general.maxThreads 2\nopen_checkpoint W:/results/compensated/design.dcp\nwrite_bitstream W:/results/compensated/Compensated_Aux4Phase.bit\nclose_design\nputs "COMPENSATED_BIT_COMPLETE"\n',encoding='ascii')
    with (ROOT/'logs/generate_bit_console.log').open('wb') as log:
        subprocess.run(['cmd.exe','/d','/c','F:/Xilinx/Vivado/2022.2/bin/vivado.bat','-mode','batch','-source',str(script),'-log','generate_bit.log','-journal','generate_bit.jou'],cwd=ROOT/'logs',stdout=log,stderr=subprocess.STDOUT,check=True)
    assert out.exists()
    result['bit_generated']=True;result['bit_sha256']=sha(out);result['dcp_sha256']=sha(dcp)
    metadata=dict(part='xc7k325tffg900-2',vivado='2022.2',clocks_mhz={'sys':100,'tdc':500,'fifo_read':100},tdc_phases_deg=[0,90,180,270],rtl_source_commit=result['rtl_source_commit'],compensation_source_commit=result['previous_compensated_commit'],parameters_csv='inputs/frozen_compensation.csv',parameters_csv_sha256=sha(ROOT/'inputs/frozen_compensation.csv'),compensation_generics=(ROOT/'inputs/compensation_params.tcl').read_text(encoding='utf-8'),generated_time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),simulation_report='results/compensated/gate_full/VALIDATION.json',final_report='RESULTS.md',bit_sha256=result['bit_sha256'],dcp_sha256=result['dcp_sha256'],global_ILA2_timing_limit_retained=True)
    (ROOT/'results/compensated/BIT_METADATA.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('COMPENSATED_BIT_GENERATED',out.stat().st_size,flush=True)

if __name__=='__main__':main()

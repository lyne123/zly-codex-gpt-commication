"""最小复用已验证构建流程；只切换冻结补偿generic和增量参考。"""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path('W:/');PREV=Path('X:/')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    stage=json.loads((ROOT/'results/RTL_STAGE_GATE.json').read_text());assert stage['rtl_pass']
    for p in (ROOT/'rtl').glob('*.v'):assert sha(p)==stage['rtl_sha256'][p.name]==sha(PREV/'rtl'/p.name)
    shutil.copytree(PREV/'build/ip_cache',ROOT/'build/ip_cache',dirs_exist_ok=True)
    text=(PREV/'scripts/register_ip.tcl').read_text(encoding='utf-8').replace('aux_baseline','aux_compensated')
    (ROOT/'scripts/register_ip.tcl').write_text(text,encoding='utf-8')
    text=(PREV/'scripts/build_aux.tcl').read_text(encoding='utf-8')
    text=text.replace('set out $root/results/baseline','set out $root/results/compensated').replace('aux_baseline','aux_compensated')
    text=text.replace('synth_design -top','source $root/inputs/compensation_params.tcl\nsynth_design -top').replace('-generic ENABLE_SKEW_COMP=0','-generic $compensation_generics')
    text=text.replace('U:/results/optimized/baseline/design.dcp','X:/results/baseline/design.dcp').replace('export_aux.tcl','export_compensated.tcl')
    (ROOT/'scripts/build_compensated.tcl').write_text(text,encoding='utf-8')
    text=(PREV/'scripts/export_aux.tcl').read_text(encoding='utf-8')
    text=text.replace('write_bitstream $out/Baseline_Aux4Phase.bit','''# BIT须等待完整MAX-SDF、补偿及核心时序验收通过后单独生成。
report_timing -from [get_cells -hier -filter {NAME =~ u_tdc_time_locate/*}] -delay_type max -max_paths 100 -path_type full_clock_expanded -input_pins -file $out/locate_setup_top100.rpt
report_timing -from [get_cells -hier -filter {NAME =~ u_tdc_time_locate/*}] -delay_type min -max_paths 50 -path_type full_clock_expanded -input_pins -file $out/locate_hold_top50.rpt''')
    text=text.replace('variant=Baseline','variant=Compensated').replace('ENABLE_SKEW_COMP=0','ENABLE_SKEW_COMP=1')
    (ROOT/'scripts/export_compensated.tcl').write_text(text,encoding='utf-8')
    paths=list((ROOT/'rtl').glob('*.v'))+list((ROOT/'inputs/ip').rglob('*.xci'))+[ROOT/'inputs/combine.xdc',ROOT/'inputs/frozen_compensation.csv',ROOT/'inputs/compensation_params.tcl',PREV/'results/baseline/design.dcp']
    (ROOT/'inputs/IMPLEMENTATION_SHA256.json').write_text(json.dumps({str(p):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in paths},indent=2),encoding='utf-8')
    print('RTL_STAGE_PASS; BUILD_READY; BIT generation deferred')

if __name__=='__main__':main()

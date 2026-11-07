"""核心STA及用户范围内最小/完整MAX-SDF都通过后，导出NoAux BIT/LTX；不烧录。"""
from pathlib import Path
import hashlib,json,shutil,subprocess
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_noaux_20261107_04'
IMPL=WORK/'implementation'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
scope=load(TASK/'results/SCOPED_RTL_GATE.json');assert scope['user_scope_confirmed'] and scope['pass_all']
gate=(IMPL/'TIMING_GATE.txt').read_text(encoding='utf-8')
assert 'core_setup_negative=0' in gate and 'core_hold_negative=0' in gate and 'ENABLE_AUX_CONFIRM=0' in gate
annotation=load(TASK/'results/sdf/noaux/ANNOTATION.json')
assert annotation['annotation_pass'] and annotation['timing_checks_enabled'] and annotation['DCP_sha256']==sha(IMPL/'NoAux_routed.dcp')
for dataset,n in [('minimal',112),('full',scope['scope_pulse_count'])]:
    s=load(TASK/f'results/sdf/noaux/{dataset}/SCOPED_SUMMARY.json')
    assert s['pass_all'] and s['scope_pulses']==s['scope_correct_pulses']==n,dataset
frozen=load(TASK/'inputs/SOURCE.json')
for name,digest in frozen['candidate_RTL_sha256'].items():assert sha(TASK/'rtl'/name)==sha(WORK/'rtl'/name)==digest
for name,digest in frozen['inputs_sha256'].items():assert sha(TASK/'inputs'/name)==digest
for name,digest in frozen['production_RTL_sha256'].items():assert sha(ROOT/'fpga_tdc_v3_cal_rtl'/name)==digest
out=WORK/'accepted_bit_export';assert not out.exists(),'不覆盖已有BIT导出';out.mkdir()
tcl=out/'export.tcl'
tcl.write_text(f'''# 只读打开与SDF绑定的路由DCP；禁止连接硬件或修改时序例外。
set_param general.maxThreads 1
open_checkpoint {{{(IMPL/'NoAux_routed.dcp').as_posix()}}}
if {{[get_property PART [current_design]] ne "xc7k325tffg900-2"}} {{error "器件不匹配"}}
if {{[get_property PACKAGE_PIN [get_ports pwm_in]] ne "AD23"}} {{error "PWM引脚不匹配"}}
write_debug_probes {{{(out/'NoAux.ltx').as_posix()}}}
write_bitstream {{{(out/'NoAux.bit').as_posix()}}}
close_design
puts "NOAUX_BIT_EXPORTED_NO_HARDWARE_PROGRAMMING"
''',encoding='utf-8')
with (out/'console.log').open('wb') as log:
    subprocess.run(['cmd.exe','/d','/c','F:/Xilinx/Vivado/2022.2/bin/vivado.bat','-mode','batch','-source',str(tcl),'-log',str(out/'vivado.log'),'-journal',str(out/'vivado.jou')],cwd=out,stdout=log,stderr=subprocess.STDOUT,check=True)
assert sha(IMPL/'NoAux_routed.dcp')==annotation['DCP_sha256']
dest=TASK/'implementation';dest.mkdir(exist_ok=True)
for name in ['NoAux.bit','NoAux.ltx']:
    assert not (dest/name).exists();shutil.copy2(out/name,dest/name)
manifest=dict(pass_all=True,acceptance_scope='input high and low >=2000ps',ENABLE_AUX_CONFIRM=0,
    extra_cycles_vs_Corrected=0,DCP_sha256=annotation['DCP_sha256'],hardware_programmed=False,
    original_RTL_supplemental_FAIL_preserved=True,
    files={name:dict(size=(dest/name).stat().st_size,sha256=sha(dest/name)) for name in ['NoAux.bit','NoAux.ltx']})
(dest/'BIT_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('NOAUX_BIT_EXPORTED_WITH_MATCHING_LTX_NO_PROGRAMMING',flush=True)

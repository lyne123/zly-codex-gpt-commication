"""验收门全部通过后，从与SDF相同的最终DCP生成BIT/LTX，不连接板卡。"""
from pathlib import Path
import hashlib,json,shutil,subprocess

TASK=Path(__file__).resolve().parents[1]
ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
IMPL=WORK/'implementation_fifo_reuse2'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def load(p):return json.loads(p.read_text(encoding='utf-8'))

assert 'core_negative_endpoints=0' in (IMPL/'TIMING_GATE.txt').read_text()
for name in ['guard','replay','backend']:
    assert load(TASK/f'results/I_confirmation_pipe/{name}/SUMMARY.json')['pass_all'],name
for delay in [0,250,500]:
    r=load(TASK/f'results/I_confirmation_pipe/pwm_lut{delay}/SUMMARY.json')
    assert r['functional_pass'] and r['width_tolerance_pass'] and r['F_equal_after_known_delay']
annotation=load(TASK/'results/sdf/corrected/ANNOTATION.json')
assert annotation['annotation_pass'] and annotation['timing_checks_enabled']
assert annotation['DCP_sha256']==sha(IMPL/'corrected_routed.dcp')
for dataset,n in [('minimal',112),('full',3512)]:
    r=load(TASK/f'results/sdf/corrected/{dataset}/SUMMARY.json')
    assert r['MAX_SDF_pass'] and r['correct_pairs']==n and r['FIFO_outputs']==n,dataset
subprocess.run(['python',str(TASK/'scripts/audit_frozen_inputs.py')],check=True)
out=WORK/'accepted_bit_export'
assert not out.exists(),'不覆盖已生成BIT'
out.mkdir()
tcl=out/'export.tcl'
tcl.write_text(f'''# 只读打开最终路由结果，禁止重新实现或连接硬件。
set_param general.maxThreads 1
open_checkpoint {{{(IMPL/'corrected_routed.dcp').as_posix()}}}
if {{[get_property PART [current_design]] ne "xc7k325tffg900-2"}} {{error "器件不匹配"}}
if {{[get_property PACKAGE_PIN [get_ports pwm_in]] ne "AD23"}} {{error "输入引脚不匹配"}}
write_debug_probes {{{(out/'Corrected.ltx').as_posix()}}}
write_bitstream {{{(out/'Corrected.bit').as_posix()}}}
close_design
puts "ACCEPTED_BIT_EXPORTED_NO_HARDWARE_ACCESS"
''',encoding='utf-8')
with (out/'console.log').open('wb') as log:
    subprocess.run(['cmd.exe','/d','/c','F:/Xilinx/Vivado/2022.2/bin/vivado.bat','-mode','batch','-source',str(tcl),'-log',str(out/'vivado.log'),'-journal',str(out/'vivado.jou')],cwd=out,stdout=log,stderr=subprocess.STDOUT,check=True)
assert sha(IMPL/'corrected_routed.dcp')==annotation['DCP_sha256']
dest=TASK/'implementation';dest.mkdir(exist_ok=True)
for name in ['Corrected.bit','Corrected.ltx']:
    assert not (dest/name).exists()
    shutil.copy2(out/name,dest/name)
manifest=dict(pass_all=True,hardware_programmed=False,DCP_sha256=annotation['DCP_sha256'],files={name:dict(size=(dest/name).stat().st_size,sha256=sha(dest/name)) for name in ['Corrected.bit','Corrected.ltx']})
(dest/'BIT_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('ACCEPTED_CORRECTED_BIT_EXPORTED_NO_PROGRAMMING',flush=True)

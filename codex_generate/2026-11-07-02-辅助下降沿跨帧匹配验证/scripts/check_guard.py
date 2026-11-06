"""检查实际RTL保护条件与全部相位/slot/claimed组合，保留失败日志。"""
from pathlib import Path
import json,shutil,subprocess,os
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02'
variant=os.environ.get('TDC_GUARD_VARIANT','E_guarded')
out=TASK/'results'/('guard' if variant=='E_guarded' else 'guard_'+variant);out.mkdir(exist_ok=True)
shutil.copy2(TASK/'sim/tb_guard_properties.sv',WORK/'sim/tb_guard_properties.sv')
shutil.copy2(TASK/'sim/functional_models.v',WORK/'sim/functional_models.v')
args=['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_guard_properties','-o',str(WORK/'guard.vvp'),str(WORK/'sim/tb_guard_properties.sv'),str(WORK/'sim/functional_models.v'),str(WORK/variant/'tdc_fine_layer.v')]
with (out/'compile.log').open('wb') as f:subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True)
with (out/'simulation.log').open('wb') as f:subprocess.run(['F:/iverilog/bin/vvp.exe',str(WORK/'guard.vvp')],stdout=f,stderr=subprocess.STDOUT,check=True)
assert 'GUARD_PROPERTIES_PASS cases=262144' in (out/'simulation.log').read_text()
(out/'SUMMARY.json').write_text(json.dumps(dict(pass_all=True,cases=262144,scope='实际RTL组合边界保护条件；不代表模拟器件物理传播'),ensure_ascii=False,indent=2),encoding='utf-8')
print('GUARD_PROPERTIES_PASS 262144')

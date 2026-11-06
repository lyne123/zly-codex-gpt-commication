"""验证新增流水下非零配对错误事件和FIFO错误序列，不作为真实测量数据。"""
from pathlib import Path
import json,shutil,subprocess
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
out=WORK/'backend_check';out.mkdir(exist_ok=True);dest=TASK/'results/I_confirmation_pipe/backend';dest.mkdir(exist_ok=True)
shutil.copy2(TASK/'sim/tb_backend.sv',WORK/'sim/tb_backend.sv')
args=['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_backend','-I',str(WORK/'sim'),'-o',str(out/'sim.vvp'),str(WORK/'sim/tb_backend.sv'),str(WORK/'sim/functional_models.v')]+list(map(str,sorted((WORK/'I_confirmation_pipe').glob('*.v'))+sorted((WORK/'F_renamed').glob('*.v'))))
for name,cmd in [('compile',args),('simulation',['F:/iverilog/bin/vvp.exe',str(out/'sim.vvp')])]:
    with (dest/(name+'.log')).open('wb') as f:subprocess.run(cmd,cwd=WORK,stdout=f,stderr=subprocess.STDOUT,check=True)
log=(dest/'simulation.log').read_text();assert 'BACKEND_ERROR_WRAP_PASS' in log and 'fifo_error=2' in log and 'F_PIPELINE_EQUIVALENCE_PASS' in log
(dest/'SUMMARY.json').write_text(json.dumps(dict(pass_all=True,simulation_only_forced_candidates=True,repeat_rise=1,orphan_fall=1,out_of_range_fine_code_rejected=True,wrap_pair_checked=True,FIFO_error_events_equal=2)),encoding='utf-8')
print('BACKEND_ERROR_FIFO_AND_WRAP_PASS')

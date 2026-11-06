"""I专用双实例检查：500MHz整组相对F延后一拍，100MHz按FIFO序列比较。"""
from pathlib import Path
import shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
shutil.copy2(TASK/'sim/miter_pipe_checks.svh',WORK/'sim/miter_pipe_checks.svh')
for name in ['tb_pwm','tb_replay']:
    text=(TASK/'sim'/(name+'.sv')).read_text(encoding='utf-8')
    assert text.count('`include "miter_checks.svh"')==1
    text=text.replace('`include "miter_checks.svh"','`include "miter_pipe_checks.svh"')
    (TASK/'sim'/(name+'_I.sv')).write_text(text,encoding='utf-8');shutil.copy2(TASK/'sim'/(name+'_I.sv'),WORK/'sim'/(name+'_I.sv'))
print('I_PIPE_MITER_PREPARED; original input files unchanged')

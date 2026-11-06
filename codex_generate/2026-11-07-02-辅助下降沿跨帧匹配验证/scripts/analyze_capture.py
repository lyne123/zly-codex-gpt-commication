"""从冻结真实CSV生成独立可审查的位序/逐拍数据；不修改原始记录。"""
from pathlib import Path
import csv,hashlib,json,shutil
from capture_io import read_capture,column
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
data=read_capture(TASK/'inputs/TRIGGER_A.csv');rows=[]
for i,r in enumerate(data):
    aux=r[column(r,'debug_aux_q')];raw=r[column(r,'debug_raw_q')]
    pipe=r[column(r,'debug_pipeline_q')];ctrl=r[column(r,'debug_control_q')]
    v=dict(sample=i,relative_trigger_ps=(i-768)*2000,ordered_samples=f'{aux&15:04b}',
        fall_slots=f'{(aux>>11)&15:04b}',fall_now=f'{(aux>>19)&15:04b}',fall_previous=f'{(aux>>27)&15:04b}',
        claimed_previous=f'{(aux>>35)&15:04b}',claimed_now=f'{(aux>>43)&15:04b}',fall_match=f'{(aux>>51)&15:04b}')
    for j,phase in enumerate([90,180,270,0]):
        p=(raw>>(j*10))&1023;v[f'type{phase}']=f'{p>>8:02b}';v[f'code{phase}']=p&255
        v[f'final{phase}']=f'{(pipe>>(29+2*j))&3:02b}'
    v.update(frame_ready=(pipe>>37)&1,sync_valid=(pipe>>12)&1,sync_mask=f'{pipe&15:04b}',
        candidate_valid=(pipe>>23)&1,candidate_type=(pipe>>24)&1,
        timestamp_valid=(ctrl>>12)&1,timestamp_type=(ctrl>>13)&1,error_valid=(ctrl>>2)&1,error_code=(ctrl>>3)&15)
    rows.append(v)
for name,selected in [('EVENT_TRACE.csv',rows),('KEY_WINDOW.csv',[r for r in rows if 717<=r['sample']<=768])]:
    with (TASK/'results'/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(selected)
assert rows[728]['fall_slots']=='1000' and rows[728]['fall_previous']=='0000'
assert rows[730]['fall_now']=='1000' and rows[731]['fall_previous']=='1000'
assert rows[731]['type0']=='10' and rows[731]['code0']==13 and rows[731]['fall_match']=='0111'
assert rows[732]['sync_mask']=='0000'
probe=ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02/input_paths'
if probe.exists():shutil.copytree(probe,TASK/'results/input_paths',dirs_exist_ok=True)
else:assert (TASK/'results/input_paths/INPUT_PATHS.csv').exists(),'归档中缺少原只读路径证据'
print('REAL_CAPTURE_DECODED 1024 samples; radix=UNSIGNED; failure=sample731')

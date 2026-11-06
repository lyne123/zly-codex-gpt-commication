"""复用实际AD23生产版已通过的FIFO物理位置，不改IP配置、网表逻辑或时序例外。"""
from pathlib import Path
import csv,hashlib,json,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
src=ROOT/'codex_generate/2026-11-07-01-上板边沿配对错误ILA定位/results/before/measurement_cells.csv'
with src.open(newline='',encoding='utf-8-sig') as f:rows=[r for r in csv.DictReader(f) if r['cell'].startswith(('u_fifo_tdc_result/','u_fifo_tdc_error/','u_fifo_tdc_result_i_','u_fifo_tdc_error_i_'))]
assert len(rows)>100,len(rows)
dest=TASK/'inputs/production_fifo_placement.csv';assert not dest.exists(),'禁止覆盖物理参考'
with dest.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=['cell','ref','loc','bel']);w.writeheader();w.writerows(rows)
shutil.copy2(dest,WORK/'production_fifo_placement.csv')
(TASK/'inputs/FIFO_PLACEMENT_SOURCE.json').write_text(json.dumps(dict(source=str(src),source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
    reference_DCP='实际AD23生产DCP',reference_DCP_sha256='9ff43fa9bd3cdb776fa7b30820b75d026a0d761da04ab83e83fed68db2846425',
    cells=len(rows),IP_configuration_changed=False,timing_exception_added=False),ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(TASK/'scripts/restore_fifo_placement.tcl',WORK/'restore_fifo_placement.tcl')
print('PRODUCTION_FIFO_PLACEMENT_FROZEN cells=',len(rows))

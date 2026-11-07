"""完整RTL或用户确认范围的RTL门通过后准备一次实现，保留范围外失败。"""
from pathlib import Path
import hashlib,json,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_noaux_20261107_04'
OLD=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
PREV=ROOT/'codex_generate/2026-11-07-03-辅助跨帧匹配时序优化'
gate=json.loads((TASK/'results/RTL_GATE.json').read_text(encoding='utf-8'))
scope=json.loads((TASK/'results/SCOPED_RTL_GATE.json').read_text(encoding='utf-8'))
assert scope['user_scope_confirmed'] and scope['pass_all'],'用户确认范围的RTL门未通过'
assert hashlib.sha256((TASK/'results/RTL_GATE.json').read_bytes()).hexdigest()==scope['original_RTL_GATE_sha256'],'不得改写原完整FAIL记录'
assert not (WORK/'implementation').exists(),'不重复覆盖实现'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
frozen=json.loads((TASK/'inputs/SOURCE.json').read_text(encoding='utf-8'))
for name,digest in frozen['candidate_RTL_sha256'].items():assert sha(TASK/'rtl'/name)==sha(WORK/'rtl'/name)==digest
for name,digest in frozen['production_RTL_sha256'].items():assert sha(ROOT/'fpga_tdc_v3_cal_rtl'/name)==digest
for ip in ['clk_wiz_0','fifo_tdc_result','ila_2','ila_3']:
    # 复制配置而不复制缓存；原生成产品只读复用，独立注册目录承接新运行的输出。
    target=WORK/f'registered/aux_compensated.srcs/sources_1/ip/{ip}';target.mkdir(parents=True)
    shutil.copy2(TASK/f'inputs/ip/{ip}/{ip}.xci',target/(ip+'.xci'))
shutil.copy2(OLD/'export_timing_proc.tcl',WORK/'export_timing_proc.tcl')
shutil.copy2(OLD/'export_timing_proc.tcl',TASK/'scripts/export_timing_proc.tcl')
source=PREV/'implementation/corrected_routed.dcp'
assert sha(source)=='01004b1502ef357304503269eaba73c9e41415456b58ecac76c393a53a6d9584'
shutil.copy2(source,WORK/'reference_corrected.dcp')
shutil.copy2(TASK/'scripts/build_noaux.tcl',WORK/'build_noaux.tcl')
(WORK/'RTL_APPROVED.flag').write_text('SCOPED_RTL_GATE pass_all=true; high_and_low_min_ps=2000; original_full_RTL_matrix_pass=false; original_stimulus_unchanged\n',encoding='ascii')
print('NOAUX_IMPLEMENTATION_PREPARED; frozen inputs; 578 FIFO placements; no hardware access')

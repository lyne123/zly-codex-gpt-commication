"""从指定提交冻结输入，只在独立候选副本增加编译期辅助确认旁路。"""
from pathlib import Path
import difflib,hashlib,json,re,shutil,subprocess

TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
PREV=ROOT/'codex_generate/2026-11-07-03-辅助跨帧匹配时序优化'
REPO=PREV/'github';BASE='d8b691b65316246567696cdbf8abd4e0f30950ee'
OLD='codex_generate/2026-11-07-03-辅助跨帧匹配时序优化/'
WORK=ROOT/'codex_generate/.vivado_work/tdc_noaux_20261107_04'
assert not (TASK/'inputs/SOURCE.json').exists(),'不覆盖已有任务输入'
for d in ['reference/rtl','rtl','inputs','scripts','sim','results','logs']: (TASK/d).mkdir(parents=True,exist_ok=True)
WORK.mkdir(parents=True,exist_ok=False)

def blob(name):return subprocess.check_output(['git','show',BASE+':'+OLD+name],cwd=REPO)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

names=['tdc_fine_layer.v','tdc_meas_top.v','tdc_time_candicate.v','tdc_time_locate.v','tdc_time_merge.v']
for name in names:
    data=blob('variants/I_confirmation_pipe/'+name)
    (TASK/'reference/rtl'/name).write_bytes(data);(TASK/'rtl'/name).write_bytes(data)
for name in ['full.txt','full_truth.csv','PWM_INPUT.txt','PWM_TRUTH.csv','minimal.txt','minimal_truth.csv','SDF_INPUT_MANIFEST.json','frozen_event_association.json','frozen_compensation.csv','compensation_params.tcl','combine_AD23.xdc','production_fifo_placement.csv','FIFO_PLACEMENT_SOURCE.json']:
    (TASK/'inputs'/name).write_bytes(blob('inputs/'+name))
for ip in ['clk_wiz_0','fifo_tdc_result','ila_2','ila_3']:
    folder=TASK/'inputs/ip'/ip;folder.mkdir(parents=True)
    (folder/(ip+'.xci')).write_bytes(blob(f'inputs/ip/{ip}/{ip}.xci'))
for name in ['functional_models.v','compensation_parameters.vh']:(TASK/'sim'/name).write_bytes(blob('sim/'+name))
# 冻结既有分析公式和库映射；不重新提取补偿或事件关联偏移。
(TASK/'scripts/pwm_analysis_reference.py').write_bytes(blob('scripts/pwm_analysis.py'))
fine=TASK/'rtl/tdc_fine_layer.v';text=fine.read_text(encoding='utf-8')
old='    parameter integer ENABLE_AUX_4PHASE = 1 // 0: 原单相辅助通路；1: 四相有序采样'
assert text.count(old)==1
text=text.replace(old,old.replace(' = 1 //',' = 1, //')+'\n    parameter integer ENABLE_AUX_CONFIRM = 1 // 1保留原确认；0仅使用TDL已筛选类型，流水延迟不变')
old='            pipe_legacy_types<={final_type0,final_type270,final_type180,final_type90};'
assert text.count(old)==1
text=text.replace(old,'''            // 旁路复用原确认级的类型寄存器，与pipe_fine_codes严格同帧同拍。
            // pack中的类型已经过各TDL的极性检测和code_in_range筛选。
            pipe_legacy_types<=ENABLE_AUX_CONFIRM ?
                {final_type0,final_type270,final_type180,final_type90} :
                {pack0_d1[9:8],pack270_to90[9:8],pack180_d1[9:8],pack90_d2[9:8]};''')
assert text.count('sync_edge_polarity <= ENABLE_AUX_4PHASE ?')==1
assert text.count('sync_edge_valid <= ENABLE_AUX_4PHASE ?')==1
text=text.replace('sync_edge_polarity <= ENABLE_AUX_4PHASE ?','sync_edge_polarity <= (ENABLE_AUX_CONFIRM && ENABLE_AUX_4PHASE) ?')
text=text.replace('sync_edge_valid <= ENABLE_AUX_4PHASE ?','sync_edge_valid <= (ENABLE_AUX_CONFIRM && ENABLE_AUX_4PHASE) ?')
fine.write_text(text,encoding='utf-8')
top=TASK/'rtl/tdc_meas_top.v';text=top.read_text(encoding='utf-8')
text=text.replace('    parameter integer TAP_PS = 10,','    parameter integer TAP_PS = 10,\n    parameter integer ENABLE_AUX_CONFIRM = 1, // 编译期对照开关；NoAux构建固定为0，默认保持原行为')
old='tdc_fine_layer #(\n    .CARRY_NUM(CARRY_NUM)'
assert text.count(old)==1;text=text.replace(old,'tdc_fine_layer #(\n    .ENABLE_AUX_CONFIRM(ENABLE_AUX_CONFIRM),\n    .CARRY_NUM(CARRY_NUM)')
top.write_text(text,encoding='utf-8')
diff=[]
for name in names:
    diff.extend(difflib.unified_diff((TASK/'reference/rtl'/name).read_text(encoding='utf-8').splitlines(True),(TASK/'rtl'/name).read_text(encoding='utf-8').splitlines(True),fromfile='aux_on/'+name,tofile='parameterized/'+name))
(TASK/'RTL.diff').write_text(''.join(diff),encoding='utf-8')
original=(TASK/'reference/rtl/tdc_fine_layer.v').read_text(encoding='utf-8');changed=fine.read_text(encoding='utf-8')
assert original[original.index('module tdc_phase_tdl_encoder'):]==changed[changed.index('module tdc_phase_tdl_encoder'):]
for name in ['tdc_time_candicate.v','tdc_time_locate.v','tdc_time_merge.v']:assert sha(TASK/'rtl'/name)==sha(TASK/'reference/rtl'/name)
for folder in ['rtl','sim','inputs']:shutil.copytree(TASK/folder,WORK/folder)
# 参考模块仅改名以容纳同一仿真的三个完整顶层，原始副本不改写。
renamed=WORK/'reference_renamed';renamed.mkdir()
modules=[]
for p in (TASK/'reference/rtl').glob('*.v'):modules+=re.findall(r'^module\s+(\w+)',p.read_text(encoding='utf-8'),re.M)
for p in (TASK/'reference/rtl').glob('*.v'):
    s=p.read_text(encoding='utf-8')
    for name in sorted(modules,key=len,reverse=True):s=re.sub(r'\b'+name+r'\b',name+'_reference',s)
    (renamed/p.name).write_text(s,encoding='utf-8')
manifest=dict(base_commit=BASE,source_RTL_sha256={name:sha(TASK/'reference/rtl'/name) for name in names},
    candidate_RTL_sha256={name:sha(TASK/'rtl'/name) for name in names},
    production_RTL_sha256={name:sha(ROOT/'fpga_tdc_v3_cal_rtl'/name) for name in names},
    phase_encoder_and_CARRY4_unchanged=True,candidate_locate_merge_unchanged=True,
    rise_range_inclusive=[1,60],fall_range_inclusive=[5,63],
    previous_confirmation_pipeline_retained=True,additional_latency_cycles=0,
    NoAux_generic='ENABLE_AUX_CONFIRM=0',AuxOn_generic='ENABLE_AUX_CONFIRM=1',
    runtime_switch=False,hardware_programming_authorized=False,work=str(WORK),
    inputs_sha256={p.relative_to(TASK/'inputs').as_posix():sha(p) for p in (TASK/'inputs').rglob('*') if p.is_file()})
(TASK/'inputs/SOURCE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
index=ROOT/'codex_generate/README.md';s=index.read_text(encoding='utf-8');assert TASK.name not in s
index.write_text(s+f'\n2026-11-07-04：[去除辅助判断对照测试]({TASK.name}/README.md)。\n',encoding='utf-8')
print('NOAUX_PREPARED; 2 RTL files; frozen thresholds; zero extra pipeline; production untouched')

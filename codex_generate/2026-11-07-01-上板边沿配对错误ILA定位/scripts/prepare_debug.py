"""冻结当前上板源码，仅在独立副本导出观测端口；不改正式工程。"""
from pathlib import Path
import difflib, hashlib, json, shutil

TASK = Path(__file__).resolve().parents[1]
ROOT = TASK.parents[1]
OLD = ROOT/'codex_generate/2026-11-05-05-四相TDC核心时序优化'
BOARD = ROOT/'codex_generate/2026-11-06-02-PWM-AD23'
WORK = ROOT/'codex_generate/.vivado_work/tdc_edge_20261107_01'

def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old,new)

def main():
    assert not (TASK/'inputs/SOURCE.json').exists(), '输入已冻结，禁止覆盖'
    for folder in ['inputs','rtl','scripts','logs','results','sim']:
        (TASK/folder).mkdir(parents=True,exist_ok=True)
    WORK.mkdir(parents=True,exist_ok=True)
    expected=json.loads((BOARD/'inputs/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))['formal_RTL_sha256']
    diffs=[]
    for name,digest in expected.items():
        p=ROOT/'fpga_tdc_v3_cal_rtl'/name
        assert sha(p)==digest, f'当前上板源码不匹配: {name}'
        before=p.read_text(encoding='utf-8'); after=before
        shutil.copy2(p,TASK/'inputs'/name)
        if name=='tdc_fine_layer.v':
            after=replace_once(after,'output reg         sync_valid          // 四相数据流水线准备完成',
                'output wire [39:0] debug_raw_packets,\n    output wire [63:0] debug_aux,\n    output wire [7:0] debug_final_types,\n    output wire debug_frame_ready,\n    output reg         sync_valid          // 四相数据流水线准备完成')
            # 只读端口均接已有信号；270支路由0°影子寄存器采集，STA检查相关相位路径。
            marker='    wire frame_ready = ready0_d1 & ready90_d2 & ready180_d1 & ready270_to90;'
            after=replace_once(after,marker,marker+'\n    assign debug_raw_packets = {pack0_d1,pack270_to90,pack180_d1,pack90_d2};\n    assign debug_frame_ready = frame_ready;')
            marker='        assign aux_fall_match[3] = |fall_now;'
            aux='''
        // 新增只读调试总线；所有位的来源在ILA_SIGNAL_MAP中逐项定义。
        assign debug_aux = {9'd0, aux_fall_match, aux_rise_match,
            fall_claimed_now, rise_claimed_now, fall_claimed_previous, rise_claimed_previous,
            fall_previous, rise_previous, fall_now, rise_now,
            aux_fall_slots, aux_rise_slots, ordered_ready, armed, previous_sample, ordered_samples};'''
            after=replace_once(after,marker,marker+aux)
            marker='    wire [1:0] final_type270 = confirm_edge(pack270_to90[9:8],    aux_rise_match[2], aux_fall_match[2]);'
            after=replace_once(after,marker,marker+'\n    assign debug_final_types = {final_type0,final_type270,final_type180,final_type90};')
        elif name=='tdc_time_merge.v':
            after=replace_once(after,'output reg  [3:0]               error_code',
                'output wire debug_rise_pending,\n    output wire debug_in_range,\n    output wire [COARSE_W+10:0] debug_rise_timestamp,\n    output reg  [3:0]               error_code')
            marker='    wire in_range = (timestamp_ps < WRAP_PS);'
            after=replace_once(after,marker,marker+'\n    // 只读导出原配对状态和最近上升沿，不参与任何原逻辑反馈。\n    assign debug_rise_pending = rise_pending;\n    assign debug_in_range = in_range;\n    assign debug_rise_timestamp = rise_timestamp_ps;')
        elif name=='tdc_meas_top.v':
            marker='wire [3:0] sync_edge_valid;'
            after=replace_once(after,marker,marker+'\nwire [39:0] debug_raw_packets;\nwire [63:0] debug_aux;\nwire [7:0] debug_final_types;\nwire debug_frame_ready;\nwire debug_rise_pending, debug_in_range;\nwire [TIME_W-1:0] debug_rise_timestamp;')
            marker='    .sync_edge_valid(sync_edge_valid),'
            after=replace_once(after,marker,marker+'\n    .debug_raw_packets(debug_raw_packets),\n    .debug_aux(debug_aux),\n    .debug_final_types(debug_final_types),\n    .debug_frame_ready(debug_frame_ready),')
            start=after.index('    ila_2 u_ila2 ('); end=after.index('\n);',start)+3
            after=after[:start]+'    // 原500MHz窄ILA仅在Debug副本中替换为下方观测实例。'+after[end:]
            marker='    .error_code           (error_event_code)'
            after=replace_once(after,marker,'    .debug_rise_pending(debug_rise_pending),\n    .debug_in_range(debug_in_range),\n    .debug_rise_timestamp(debug_rise_timestamp),\n'+marker)
            insert=(TASK/'scripts/debug_top_fragment.vh').read_text(encoding='utf-8')
            after=replace_once(after,'\nendmodule','\n'+insert+'\nendmodule')
        (TASK/'rtl'/name).write_text(after,encoding='utf-8')
        diffs.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='production/'+name,tofile='debug/'+name))
    for name in ['compensation_params.tcl','frozen_compensation.csv']:
        shutil.copy2(OLD/'inputs'/name,TASK/'inputs'/name)
    shutil.copy2(BOARD/'inputs/combine_AD23.xdc',TASK/'inputs/combine_AD23.xdc')
    shutil.copy2(ROOT/'fpga_tdc_v3_cal_rtl/board_pins.xdc',TASK/'inputs/board_pins.xdc')
    (TASK/'RTL.diff').write_text(''.join(diffs),encoding='utf-8')
    # 真实ASCII工作目录避开旧版Vivado中文路径问题，不创建盘符映射。
    for tree in ['aux_compensated.srcs','aux_compensated.gen']:
        shutil.copytree(OLD/'build/registered'/tree,WORK/'registered'/tree,dirs_exist_ok=True)
    shutil.copytree(OLD/'build/ip_cache',WORK/'ip_cache',dirs_exist_ok=True)
    shutil.copytree(TASK/'rtl',WORK/'rtl',dirs_exist_ok=True)
    for name in ['compensation_params.tcl','combine_AD23.xdc']:
        shutil.copy2(TASK/'inputs'/name,WORK/name)
    shutil.copy2(BOARD/'results/design_AD23.dcp',WORK/'production_AD23.dcp')
    shutil.copy2(TASK/'scripts/build_debug.tcl',WORK/'build_debug.tcl')
    record=dict(source_commit='ba978229094a8621b30770177727d8e70b831a74',
        git_base_commit='31090be88d0fef94835f69a6edcff4e447328220',
        source_note='当前正式RTL与05源Commit一致；实际生产实现为本地AD23引脚ECO版本，非历史SDF版本替代',
        production_bit=str(BOARD/'results/TDC_Compensated_ILA100M_PWM_AD23.bit'),
        production_bit_sha256=sha(BOARD/'results/TDC_Compensated_ILA100M_PWM_AD23.bit'),
        reference_dcp=str(BOARD/'results/design_AD23.dcp'),reference_dcp_sha256=sha(BOARD/'results/design_AD23.dcp'),
        formal_RTL_sha256=expected,formal_RTL_modified=False,work=str(WORK),no_drive_mapping=True,
        debug_note='只读端口、影子寄存器、独立计数器与ILA；没有测量反馈')
    (TASK/'inputs/SOURCE.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    index=ROOT/'codex_generate/README.md'
    with index.open('a',encoding='utf-8') as f:
        f.write('\n2026-11-07-01：[上板边沿配对错误ILA定位](2026-11-07-01-上板边沿配对错误ILA定位/RESULTS.md)。\n')
    print(json.dumps(record,ensure_ascii=False,indent=2))

if __name__=='__main__': main()

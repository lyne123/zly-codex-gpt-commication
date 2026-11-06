"""根据G实际负路径移除late ready的早期扇入，同拍寄存完整base匹配。"""
from pathlib import Path
import re,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
assert not (TASK/'variants/H_registered_match').exists(),'禁止覆盖候选'
text=(TASK/'variants/G_precompute/tdc_fine_layer.v').read_text(encoding='utf-8')
for name in ['r0','r180','r90','f0','f180','f90']:
    text,n=re.subn(rf'(wire {name}=)frame_ready && ',r'\1',text);assert n==1
def init(pol):
    # I0无270归属，I1有270归属，I2/I3类型，I4未扣除事件，I5整帧ready。
    value=0
    for i in range(64):
        output=(((i>>1)&1) if ((i>>2)&3)==pol else (i&1)) if i&32 else ((i>>4)&1)
        value |= output<<i
    return value
for pol,code in [('r',3),('f',2)]:
    long='rise' if pol=='r' else 'fall'
    pat=rf'LUT5 #\(\.INIT\(32\'h[0-9a-f]+\)\) u_{pol} \(\.I0\({pol}_no270\),\.I1\(!{pol}0 && {long}_suffix_now\[3\]\),\.I2\(pack270_to90\[8\]\),\.I3\(pack270_to90\[9\]\),\.I4\(frame_ready\),\.O\({long}_remaining_next\[tail\]\)\);'
    replacement=f"LUT6 #(.INIT(64'h{init(code):016x})) u_{pol} (.I0({pol}_no270),.I1(!{pol}0 && {long}_suffix_now[3]),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4({long}_suffix_now[tail]),.I5(frame_ready),.O({long}_remaining_next[tail]));"
    text,n=re.subn(pat,lambda m:replacement,text);assert n==1,(pol,'remaining')
    pat=rf'LUT5 #\(\.INIT\(32\'h[0-9a-f]+\)\) u_single_{pol} \([^;]+;'
    replacement=f"LUT6 #(.INIT(64'h{init(code):016x})) u_single_{pol} (.I0({long}_single_no270),.I1(!{pol}0 && {long}_single_now[3]),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4({long}_single_now[0]),.I5(frame_ready),.O({long}_single_next));"
    text,n=re.subn(pat,lambda m:replacement,text);assert n==1,(pol,'single')
marker='        wire [3:0] base_rise_match, base_fall_match;'
assert text.count(marker)==1
block='''        // next前缀与remaining_next属于同一输出帧；在原history边界同时寄存，不新增输出拍数。
        wire [3:0] rise_base_next,fall_base_next;
        reg [3:0] rise_base_q,fall_base_q;
        genvar match_phase;
        for(match_phase=0;match_phase<4;match_phase=match_phase+1) begin : g_base_precompute
            wire next_rise_prefix,next_fall_prefix;
            if(ALIGN_CYCLES>0) begin : g_from_history
                assign next_rise_prefix=|rise_history[ALIGN_CYCLES-1][match_phase:0];
                assign next_fall_prefix=|fall_history[ALIGN_CYCLES-1][match_phase:0];
            end else begin : g_from_input
                wire [3:0] next_rise_slots=(armed && ordered_ready) ? (ordered_samples & ~previous_slots) : 4'b0000;
                wire [3:0] next_fall_slots=(armed && ordered_ready) ? (~ordered_samples & previous_slots) : 4'b0000;
                assign next_rise_prefix=|next_rise_slots[match_phase:0];
                assign next_fall_prefix=|next_fall_slots[match_phase:0];
            end
            if(match_phase==3) begin : g_last_phase
                assign rise_base_next[match_phase]=next_rise_prefix;
                assign fall_base_next[match_phase]=next_fall_prefix;
            end else begin : g_with_previous
                localparam integer FROM=match_phase+1;
                localparam integer FROM180=(FROM<2)?2:FROM;
                localparam integer FROM90=(FROM<1)?1:FROM;
                wire r_none=!r0 && (r180 ? rise_suffix_now[FROM180] : r90 ? rise_suffix_now[FROM90] : rise_suffix_now[FROM]);
                wire f_none=!f0 && (f180 ? fall_suffix_now[FROM180] : f90 ? fall_suffix_now[FROM90] : fall_suffix_now[FROM]);
                LUT6 #(.INIT(64'hRISE_INIT)) u_r (.I0(next_rise_prefix | r_none),.I1(next_rise_prefix | (!r0 && rise_suffix_now[3])),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(next_rise_prefix | rise_suffix_now[FROM]),.I5(frame_ready),.O(rise_base_next[match_phase]));
                LUT6 #(.INIT(64'hFALL_INIT)) u_f (.I0(next_fall_prefix | f_none),.I1(next_fall_prefix | (!f0 && fall_suffix_now[3])),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(next_fall_prefix | fall_suffix_now[FROM]),.I5(frame_ready),.O(fall_base_next[match_phase]));
            end
        end
        always @(posedge clk_500m or negedge rst_n_0)
            if(!rst_n_0) begin rise_base_q<=0;fall_base_q<=0;end
            else begin rise_base_q<=rise_base_next;fall_base_q<=fall_base_next;end
'''.replace('RISE_INIT',f'{init(3):016x}').replace('FALL_INIT',f'{init(2):016x}')
text=text.replace(marker,block+marker)
for long in ['rise','fall']:
    for j in range(4):
        text,n=re.subn(rf'assign base_{long}_match\[{j}\] = [^;]+;',f'assign base_{long}_match[{j}] = {long}_base_q[{j}];',text);assert n==1
text=text.replace('back_r=!confirmed && has_r && !has_f && single_r;','back_r=!confirmed && !has_f && single_r;')
text=text.replace('back_f=!confirmed && has_f && !has_r && single_f;','back_f=!confirmed && !has_r && single_f;')
text=text.replace('// 晚到270°类型只控制末级选择；保持frame_ready=0时不扣除任何事件的原语义。','// 晚到270°类型与frame_ready只控制末级选择；ready为0时直接选未扣除的原事件统计。')
dst=TASK/'variants/H_registered_match';shutil.copytree(TASK/'variants/G_precompute',dst)
(dst/'tdc_fine_layer.v').write_text(text,encoding='utf-8');shutil.copytree(dst,WORK/'H_registered_match')
guard=(TASK/'sim/tb_guard_properties.sv').read_text(encoding='utf-8')
marker=' for(pat=0;pat<256;pat=pat+1)'
guard=guard.replace(marker,''' force dut.g_aux_4phase.base_rise_match={r_prefix[3],(r_prefix[2]|r_suffix[3]),(r_prefix[1]|r_suffix[2]),(r_prefix[0]|r_suffix[1])};
 force dut.g_aux_4phase.base_fall_match={f_prefix[3],(f_prefix[2]|f_suffix[3]),(f_prefix[1]|f_suffix[2]),(f_prefix[0]|f_suffix[1])};
'''+marker)
(TASK/'sim/tb_guard_properties_H.sv').write_text(guard,encoding='utf-8');shutil.copy2(TASK/'sim/tb_guard_properties_H.sv',WORK/'sim/tb_guard_properties_H.sv')
print('H_PREPARED; frame_ready last-level; full base matches retimed without added latency')

"""冻结F与生产Baseline，预计算现有history帧的窗口资格，保持端到端延迟。"""
from pathlib import Path
import difflib,hashlib,json,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
PREV=ROOT/'codex_generate/2026-11-07-02-辅助下降沿跨帧匹配验证'
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not (TASK/'inputs/SOURCE.json').exists(),'禁止覆盖冻结输入'
for folder in ['inputs','reference_F/rtl','production_original/rtl','variants/G_precompute','sim','logs','results']:(TASK/folder).mkdir(parents=True,exist_ok=True)
baseline=json.loads((PREV/'inputs/SOURCE.json').read_text(encoding='utf-8'))
for name,digest in baseline['formal_RTL_sha256'].items():
    assert sha(ROOT/'fpga_tdc_v3_cal_rtl'/name)==digest,name
    shutil.copy2(ROOT/'fpga_tdc_v3_cal_rtl'/name,TASK/'production_original/rtl'/name)
    shutil.copy2(PREV/'variants/F_factored'/name,TASK/'reference_F/rtl'/name)
    shutil.copy2(PREV/'variants/F_factored'/name,TASK/'variants/G_precompute'/name)
for name in ['TRIGGER_A.csv','compensation_params.tcl','frozen_compensation.csv','combine_AD23.xdc','PWM_INPUT.txt','PWM_TRUTH.csv']:
    shutil.copy2(PREV/'inputs'/name,TASK/'inputs'/name)
shutil.copytree(PREV/'inputs/ip',TASK/'inputs/ip')
for name in ['functional_models.v','compensation_parameters.vh','tb_replay.sv','tb_pwm.sv','tb_guard_properties.sv','tb_sdf.sv']:shutil.copy2(PREV/'sim'/name,TASK/'sim'/name)
for name in ['capture_io.py']:shutil.copy2(PREV/'scripts'/name,TASK/'scripts'/name)
text=(TASK/'reference_F/rtl/tdc_fine_layer.v').read_text(encoding='utf-8')
text=text.replace('wire [7:0] guarded_final_types;','wire [7:0] guarded_final_types;\n    wire [7:0] guarded_output_types;')
start=text.index('        reg [3:0] rise_claimed_previous, fall_claimed_previous;')
end=text.index('        wire [3:0] base_rise_match, base_fall_match;',start)
block='''        // claimed是当前事件与相位前缀的交集；寄存前缀后再取交集，与原逐位寄存严格同拍。
        wire [3:0] rise_cover =
            ({4{pack0_d1[9:8]==2'b11}} & 4'b1111) |
            ({4{pack270_to90[9:8]==2'b11}} & 4'b0111) |
            ({4{pack180_d1[9:8]==2'b11}} & 4'b0011) |
            ({4{pack90_d2[9:8]==2'b11}} & 4'b0001);
        wire [3:0] fall_cover =
            ({4{pack0_d1[9:8]==2'b10}} & 4'b1111) |
            ({4{pack270_to90[9:8]==2'b10}} & 4'b0111) |
            ({4{pack180_d1[9:8]==2'b10}} & 4'b0011) |
            ({4{pack90_d2[9:8]==2'b10}} & 4'b0001);
        wire [3:0] rise_claimed_now=rise_now & rise_cover;
        wire [3:0] fall_claimed_now=fall_now & fall_cover;
        reg [3:0] rise_cover_previous,fall_cover_previous;
        always @(posedge clk_500m or negedge rst_n_0)
            if(!rst_n_0) begin rise_cover_previous<=0;fall_cover_previous<=0;end
            else begin
                rise_cover_previous<=frame_ready ? rise_cover : 4'b0000;
                fall_cover_previous<=frame_ready ? fall_cover : 4'b0000;
            end
        wire [3:0] rise_claimed_previous=rise_history[ALIGN_CYCLES+1] & rise_cover_previous;
        wire [3:0] fall_claimed_previous=fall_history[ALIGN_CYCLES+1] & fall_cover_previous;
        wire [3:0] rise_previous=rise_history[ALIGN_CYCLES+1] & ~rise_claimed_previous;
        wire [3:0] fall_previous=fall_history[ALIGN_CYCLES+1] & ~fall_claimed_previous;
        function single_event;
            input [3:0] events;
            begin single_event=(|events) && ((events & (events-4'b0001))==0);end
        endfunction
        // 与now同时到达的前缀OR、后缀OR和后缀唯一标志，从既有上一级history计算。
        wire [3:0] rise_prefix_now,fall_prefix_now;
        wire [3:0] rise_suffix_now,fall_suffix_now,rise_single_now,fall_single_now;
        genvar stat;
        for(stat=0;stat<4;stat=stat+1) begin : g_stats
            if(ALIGN_CYCLES>0) begin : g_registered
                reg rp,fp,rs,fs,ru,fu;
                always @(posedge clk_500m or negedge rst_n_0)
                    if(!rst_n_0) begin rp<=0;fp<=0;rs<=0;fs<=0;ru<=0;fu<=0;end
                    else begin
                        rp<=|rise_history[ALIGN_CYCLES-1][stat:0];
                        fp<=|fall_history[ALIGN_CYCLES-1][stat:0];
                        rs<=|rise_history[ALIGN_CYCLES-1][3:stat];
                        fs<=|fall_history[ALIGN_CYCLES-1][3:stat];
                        ru<=single_event(rise_history[ALIGN_CYCLES-1]>>stat);
                        fu<=single_event(fall_history[ALIGN_CYCLES-1]>>stat);
                    end
                assign rise_prefix_now[stat]=rp;assign fall_prefix_now[stat]=fp;
                assign rise_suffix_now[stat]=rs;assign fall_suffix_now[stat]=fs;
                assign rise_single_now[stat]=ru;assign fall_single_now[stat]=fu;
            end else begin : g_no_align
                assign rise_prefix_now[stat]=|rise_now[stat:0];assign fall_prefix_now[stat]=|fall_now[stat:0];
                assign rise_suffix_now[stat]=|rise_now[3:stat];assign fall_suffix_now[stat]=|fall_now[3:stat];
                assign rise_single_now[stat]=single_event(rise_now>>stat);assign fall_single_now[stat]=single_event(fall_now>>stat);
            end
        end
        wire r0=frame_ready && pack0_d1[9:8]==2'b11;
        wire r180=frame_ready && pack180_d1[9:8]==2'b11;
        wire r90=frame_ready && pack90_d2[9:8]==2'b11;
        wire f0=frame_ready && pack0_d1[9:8]==2'b10;
        wire f180=frame_ready && pack180_d1[9:8]==2'b10;
        wire f90=frame_ready && pack90_d2[9:8]==2'b10;
        wire [3:0] rise_remaining_next,fall_remaining_next;
        reg [3:0] rise_remaining_previous,fall_remaining_previous;
        genvar tail;
        for(tail=0;tail<4;tail=tail+1) begin : g_remaining
            localparam integer FROM180=(tail<2)?2:tail;
            localparam integer FROM90=(tail<1)?1:tail;
            wire r_no270=!r0 && (r180 ? rise_suffix_now[FROM180] : r90 ? rise_suffix_now[FROM90] : rise_suffix_now[tail]);
            wire f_no270=!f0 && (f180 ? fall_suffix_now[FROM180] : f90 ? fall_suffix_now[FROM90] : fall_suffix_now[tail]);
            // 晚到270°类型只控制末级选择；保持frame_ready=0时不扣除任何事件的原语义。
            LUT5 #(.INIT(32'hRISE_INIT)) u_r (.I0(r_no270),.I1(!r0 && rise_suffix_now[3]),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(frame_ready),.O(rise_remaining_next[tail]));
            LUT5 #(.INIT(32'hFALL_INIT)) u_f (.I0(f_no270),.I1(!f0 && fall_suffix_now[3]),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(frame_ready),.O(fall_remaining_next[tail]));
        end
        wire rise_single_no270=!r0 && (r180 ? rise_single_now[2] : r90 ? rise_single_now[1] : rise_single_now[0]);
        wire fall_single_no270=!f0 && (f180 ? fall_single_now[2] : f90 ? fall_single_now[1] : fall_single_now[0]);
        wire rise_single_next,fall_single_next;
        reg rise_previous_single_q,fall_previous_single_q;
        LUT5 #(.INIT(32'hRISE_INIT)) u_single_r (.I0(rise_single_no270),.I1(!r0 && rise_single_now[3]),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(frame_ready),.O(rise_single_next));
        LUT5 #(.INIT(32'hFALL_INIT)) u_single_f (.I0(fall_single_no270),.I1(!f0 && fall_single_now[3]),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(frame_ready),.O(fall_single_next));
        always @(posedge clk_500m or negedge rst_n_0)
            if(!rst_n_0) begin
                rise_remaining_previous<=0;fall_remaining_previous<=0;
                rise_previous_single_q<=0;fall_previous_single_q<=0;
            end else begin
                rise_remaining_previous<=rise_remaining_next;fall_remaining_previous<=fall_remaining_next;
                rise_previous_single_q<=rise_single_next;fall_previous_single_q<=fall_single_next;
            end
'''
def mux_init(pol):
    return sum((((i>>1)&1) if (i&16 and ((i>>2)&3)==pol) else (i&1))<<i for i in range(32))
block=block.replace('RISE_INIT',f'{mux_init(3):08x}').replace('FALL_INIT',f'{mux_init(2):08x}')
text=text[:start]+block+text[end:]
for polarity in ['rise','fall']:
    for j in range(4):
        import re
        replacement=f'        assign base_{polarity}_match[{j}] = {polarity}_prefix_now[{j}]'+(f' | {polarity}_remaining_previous[{j+1}]' if j<3 else '')+';'
        text,n=re.subn(rf'        assign base_{polarity}_match\[{j}\] = [^;]+;',replacement,text);assert n==1
    old=f'wire {polarity}_previous_single = (|{polarity}_previous) && (({polarity}_previous & ({polarity}_previous-4\'b0001))==0);'
    assert text.count(old)==1;text=text.replace(old,f'wire {polarity}_previous_single = {polarity}_previous_single_q;')
marker='                .I3(pack270_to90[8]),.I4(pack270_to90[9]),.O(guarded_final_types[bit_id]));'
assert text.count(marker)==1
text=text.replace(marker,marker+'''
            // 将原末级frame_ready门控并入选择LUT，输出寄存器及拍数不变。
            LUT6 #(.INIT(64'hf0ccaaaa00000000)) u_output (
                .I0(if_invalid[bit_id]),.I1(if_fall[bit_id]),.I2(if_rise[bit_id]),
                .I3(pack270_to90[8]),.I4(pack270_to90[9]),.I5(frame_ready),.O(guarded_output_types[bit_id]));''')
start=text.index('            sync_edge_polarity <= frame_ready ? {')
end=text.index('\n        end\n    end\nendmodule',start)
text=text[:start]+'''            sync_edge_polarity <= ENABLE_AUX_4PHASE ? guarded_output_types :
                (frame_ready ? {final_type0,final_type270,final_type180,final_type90} : 8'd0);
            sync_edge_valid <= ENABLE_AUX_4PHASE ?
                {guarded_output_types[7],guarded_output_types[5],guarded_output_types[3],guarded_output_types[1]} :
                (frame_ready ? {final_type0[1],final_type270[1],final_type180[1],final_type90[1]} : 4'd0);'''+text[end:]
(TASK/'variants/G_precompute/tdc_fine_layer.v').write_text(text,encoding='utf-8')
models=(TASK/'sim/functional_models.v').read_text(encoding='utf-8')
models+='''
// LUT6只提供组合真值表；实际传播和检查全部使用Vivado器件SDF。
module LUT6 #(parameter [63:0] INIT=0)(input I0,I1,I2,I3,I4,I5,output O);
 assign O=INIT[{I5,I4,I3,I2,I1,I0}];
endmodule
'''
(TASK/'sim/functional_models.v').write_text(models,encoding='utf-8')
for src,dst in [(TASK/'reference_F/rtl',WORK/'F_reference'),(TASK/'variants/G_precompute',WORK/'G_precompute'),(TASK/'sim',WORK/'sim')]:shutil.copytree(src,dst)
record=dict(base_commit='0d741ec0cba376da4dc83a7069e1dfb2b28edce7',formal_RTL_sha256=baseline['formal_RTL_sha256'],
    reference_F_RTL_sha256={p.name:sha(p) for p in (TASK/'reference_F/rtl').glob('*.v')},
    real_csv_sha256=sha(TASK/'inputs/TRIGGER_A.csv'),parameters_recalculated=False,formal_RTL_modified=False,
    output_latency_cycles_added=0,work=str(WORK),existing_other_03_directory_preserved=True)
(TASK/'inputs/SOURCE.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
with (ROOT/'codex_generate/README.md').open('a',encoding='utf-8') as f:f.write(f'\n2026-11-07-03：[辅助跨帧匹配时序优化]({TASK.name}/README.md)。\n')
print('G_PREPARED; same output cycle; production RTL untouched')

"""同拍优化未收敛后增加一级专用确认流水，整组延迟并同步粗计数采样时刻。"""
from pathlib import Path
import re,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
dst=TASK/'variants/I_confirmation_pipe';assert not dst.exists(),'禁止覆盖候选'
shutil.copytree(TASK/'variants/H3_ready_precompute',dst)
text=(dst/'tdc_fine_layer.v').read_text(encoding='utf-8')
marker='    wire [7:0] guarded_output_types;'
assert text.count(marker)==1
text=text.replace(marker,marker+'''
    // 专用确认级：细码、帧ready和确认余因子在同一拍锁存，全部测量输出整组延后一拍。
    reg [31:0] pipe_fine_codes;
    reg pipe_frame_ready;
    reg [7:0] pipe_legacy_types;
    always @(posedge clk_500m or negedge rst_n_0)
        if(!rst_n_0) begin pipe_fine_codes<=0;pipe_frame_ready<=0;pipe_legacy_types<=0;end
        else begin
            pipe_fine_codes<={pack0_d1[7:0],pack270_to90[7:0],pack180_d1[7:0],pack90_d2[7:0]};
            pipe_frame_ready<=frame_ready;
            pipe_legacy_types<={final_type0,final_type270,final_type180,final_type90};
        end
''')
marker='        genvar bit_id;'
assert text.count(marker)==1
text=text.replace(marker,'''        reg [7:0] pipe_if_invalid,pipe_if_fall,pipe_if_rise;
        reg [1:0] pipe_type270;
        always @(posedge clk_500m or negedge rst_n_0)
            if(!rst_n_0) begin pipe_if_invalid<=0;pipe_if_fall<=0;pipe_if_rise<=0;pipe_type270<=0;end
            else begin
                pipe_if_invalid<=if_invalid;pipe_if_fall<=if_fall;pipe_if_rise<=if_rise;
                pipe_type270<=pack270_to90[9:8];
            end
'''+marker)
old='''                .I0(if_invalid[bit_id] & early_frame_ready),.I1(if_fall[bit_id] & early_frame_ready),.I2(if_rise[bit_id] & early_frame_ready),
                .I3(pack270_to90[8]),.I4(pack270_to90[9]),.I5(ready270_to90),.O(guarded_output_types[bit_id]));'''
new='''                .I0(pipe_if_invalid[bit_id]),.I1(pipe_if_fall[bit_id]),.I2(pipe_if_rise[bit_id]),
                .I3(pipe_type270[0]),.I4(pipe_type270[1]),.I5(pipe_frame_ready),.O(guarded_output_types[bit_id]));'''
assert text.count(old)==1;text=text.replace(old,new)
start=text.index('            all_fine_code <= {');end=text.index('            sync_edge_polarity <=',start)
text=text[:start]+'''            all_fine_code <= pipe_fine_codes;
            sync_valid <= pipe_frame_ready;
'''+text[end:]
text=text.replace('(frame_ready ? {final_type0,final_type270,final_type180,final_type90} : 8\'d0)',"(pipe_frame_ready ? pipe_legacy_types : 8'd0)")
text=text.replace("(frame_ready ? {final_type0[1],final_type270[1],final_type180[1],final_type90[1]} : 4'd0)","(pipe_frame_ready ? {pipe_legacy_types[7],pipe_legacy_types[5],pipe_legacy_types[3],pipe_legacy_types[1]} : 4'd0)")
text=text.replace('将原末级frame_ready门控并入选择LUT，输出寄存器及拍数不变。','将frame_ready门控并入选择LUT；此前专用确认级使整组测量输出增加一拍。')
(dst/'tdc_fine_layer.v').write_text(text,encoding='utf-8')
loc=(dst/'tdc_time_locate.v').read_text(encoding='utf-8')
loc=loc.replace('    parameter integer TAP_PS   = 10,','''    parameter integer TAP_PS   = 10,
    // 专用前端确认级增加一拍时，粗计数采样同样回看一拍；不改变时间戳公式或粗计数器。
    parameter integer INPUT_COARSE_DELAY = 0,''')
marker='    // Constant shift-and-add conversion from tap count directly to ps.'
assert loc.count(marker)==1
loc=loc.replace(marker,'''    reg [COARSE_W-1:0] coarse_counter_d1;
    always @(posedge clk_500m or negedge rst_n)
        if(!rst_n) coarse_counter_d1 <= {COARSE_W{1'b0}};
        else coarse_counter_d1 <= coarse_counter;
    wire [COARSE_W-1:0] coarse_for_capture = INPUT_COARSE_DELAY ? coarse_counter_d1 : coarse_counter;
`ifndef SYNTHESIS
    initial if(INPUT_COARSE_DELAY!=0 && INPUT_COARSE_DELAY!=1) $fatal(1,"仅支持零拍或一拍粗计数对齐");
`endif

'''+marker)
assert loc.count('s2_coarse    <= coarse_counter;')==1
loc=loc.replace('s2_coarse    <= coarse_counter;','s2_coarse    <= coarse_for_capture;')
(dst/'tdc_time_locate.v').write_text(loc,encoding='utf-8')
top=(dst/'tdc_meas_top.v').read_text(encoding='utf-8')
marker='    tdc_time_locate #(\n        .COARSE_W (COARSE_W),'
assert top.count(marker)==1
top=top.replace(marker,'    tdc_time_locate #(\n        .INPUT_COARSE_DELAY(1), // 与前端新增确认级同拍对齐，不重新拟合补偿。\n        .COARSE_W (COARSE_W),')
(dst/'tdc_meas_top.v').write_text(top,encoding='utf-8')
shutil.copytree(dst,WORK/'I_confirmation_pipe')
# 组合确认真值表本身不变；仍用H的完整组合保护检查。
print('I_PREPARED; +1 whole frame; coarse counter unchanged; shadow sampled at original event time')

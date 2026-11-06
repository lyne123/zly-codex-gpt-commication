// 新确认流水相对F延迟一拍；500MHz整组对齐，100MHz按FIFO事件顺序比较。
// 冻结工程时间戳/脉宽各21位，合计111位；避开Icarus层级$bits常量的编译限制。
wire [110:0] reference_500={
 refdut.all_fine_code,refdut.sync_edge_valid,refdut.sync_edge_polarity,refdut.sync_valid,
 refdut.edge_valid,refdut.edge_type_q,refdut.sel_index,refdut.chosen_code,refdut.polarity_conflict,refdut.repeat_error,
 refdut.timestamp_valid,refdut.timestamp_edge_type,refdut.timestamp_ps,refdut.pulse_width_valid,refdut.pulse_width_ps,
 refdut.error_event_valid,refdut.error_event_code,refdut.result_fifo_overflow,refdut.error_fifo_overflow};
reg [110:0] reference_500_d1=0;
integer miter_cycles=0;
always @(posedge dut.clk_500m) if(!dut.rst_n_500m) reference_500_d1<=0;else reference_500_d1<=reference_500;
always @(negedge dut.clk_500m) if(dut.rst_n_500m) begin
 #1;
 if({dut.all_fine_code,dut.sync_edge_valid,dut.sync_edge_polarity,dut.sync_valid,
     dut.edge_valid,dut.edge_type_q,dut.sel_index,dut.chosen_code,dut.polarity_conflict,dut.repeat_error,
     dut.timestamp_valid,dut.timestamp_edge_type,dut.timestamp_ps,dut.pulse_width_valid,dut.pulse_width_ps,
     dut.error_event_valid,dut.error_event_code,dut.result_fifo_overflow,dut.error_fifo_overflow} !== reference_500_d1)
     $fatal(1,"F整组延迟一拍后不等价 time=%0t",$time);
 if({dut.u_tdc_fine_layer.final_type0,dut.u_tdc_fine_layer.final_type270,dut.u_tdc_fine_layer.final_type180,dut.u_tdc_fine_layer.final_type90,
     dut.u_tdc_fine_layer.aux_rise_match,dut.u_tdc_fine_layer.aux_fall_match,
     dut.u_tdc_fine_layer.g_aux_4phase.rise_claimed_previous,dut.u_tdc_fine_layer.g_aux_4phase.fall_claimed_previous,
     dut.u_tdc_fine_layer.g_aux_4phase.rise_previous,dut.u_tdc_fine_layer.g_aux_4phase.fall_previous} !==
    {refdut.u_tdc_fine_layer.final_type0,refdut.u_tdc_fine_layer.final_type270,refdut.u_tdc_fine_layer.final_type180,refdut.u_tdc_fine_layer.final_type90,
     refdut.u_tdc_fine_layer.aux_rise_match,refdut.u_tdc_fine_layer.aux_fall_match,
     refdut.u_tdc_fine_layer.g_aux_4phase.rise_claimed_previous,refdut.u_tdc_fine_layer.g_aux_4phase.fall_claimed_previous,
     refdut.u_tdc_fine_layer.g_aux_4phase.rise_previous,refdut.u_tdc_fine_layer.g_aux_4phase.fall_previous})
     $fatal(1,"流水新增级不应改变原确认或归属规则 time=%0t",$time);
 miter_cycles=miter_cycles+1;
end
reg [20:0] ref_width_queue[0:9999],new_width_queue[0:9999];
reg [3:0] ref_error_queue[0:9999],new_error_queue[0:9999];
integer nr=0,nn=0,nc=0,er=0,en=0,ec=0;
always @(negedge dut.clk_100m) if(dut.rst_n_100m) begin
 #1;
 if(refdut.pulse_width_valid_100m) begin ref_width_queue[nr]=refdut.pulse_width_ps_100m;nr=nr+1;end
 if(dut.pulse_width_valid_100m) begin new_width_queue[nn]=dut.pulse_width_ps_100m;nn=nn+1;end
 if(refdut.error_valid_100m) begin ref_error_queue[er]=refdut.error_code_100m;er=er+1;end
 if(dut.error_valid_100m) begin new_error_queue[en]=dut.error_code_100m;en=en+1;end
 while(nc<nr && nc<nn) begin if(ref_width_queue[nc]!==new_width_queue[nc]) $fatal(1,"100MHz脉宽FIFO序列不同");nc=nc+1;end
 while(ec<er && ec<en) begin if(ref_error_queue[ec]!==new_error_queue[ec]) $fatal(1,"100MHz错误FIFO序列不同");ec=ec+1;end
end
final begin
 if(nr!=nn || er!=en) $fatal(1,"最终FIFO输出数量不等价");
 $display("F_PIPELINE_EQUIVALENCE_PASS cycles=%0d added_cycles=1 fifo_width=%0d fifo_error=%0d",miter_cycles,nn,en);
end

// 同一激励、时钟、参数下全链路逐周期比较，包含无效拍的数据保持行为。
integer miter_cycles=0;
always @(negedge dut.clk_500m) if(dut.rst_n_500m) begin
 #1;
 if({dut.all_fine_code,dut.sync_edge_valid,dut.sync_edge_polarity,dut.sync_valid,
     dut.edge_valid,dut.edge_type_q,dut.sel_index,dut.chosen_code,dut.polarity_conflict,dut.repeat_error,
     dut.timestamp_valid,dut.timestamp_edge_type,dut.timestamp_ps,dut.pulse_width_valid,dut.pulse_width_ps,
     dut.error_event_valid,dut.error_event_code,dut.result_fifo_overflow,dut.error_fifo_overflow} !==
    {refdut.all_fine_code,refdut.sync_edge_valid,refdut.sync_edge_polarity,refdut.sync_valid,
     refdut.edge_valid,refdut.edge_type_q,refdut.sel_index,refdut.chosen_code,refdut.polarity_conflict,refdut.repeat_error,
     refdut.timestamp_valid,refdut.timestamp_edge_type,refdut.timestamp_ps,refdut.pulse_width_valid,refdut.pulse_width_ps,
     refdut.error_event_valid,refdut.error_event_code,refdut.result_fifo_overflow,refdut.error_fifo_overflow})
     $fatal(1,"F全链路逐周期输出不一致 time=%0t",$time);
 if({dut.u_tdc_fine_layer.final_type0,dut.u_tdc_fine_layer.final_type270,dut.u_tdc_fine_layer.final_type180,dut.u_tdc_fine_layer.final_type90,
     dut.u_tdc_fine_layer.aux_rise_match,dut.u_tdc_fine_layer.aux_fall_match,
     dut.u_tdc_fine_layer.g_aux_4phase.rise_claimed_previous,dut.u_tdc_fine_layer.g_aux_4phase.fall_claimed_previous,
     dut.u_tdc_fine_layer.g_aux_4phase.rise_previous,dut.u_tdc_fine_layer.g_aux_4phase.fall_previous} !==
    {refdut.u_tdc_fine_layer.final_type0,refdut.u_tdc_fine_layer.final_type270,refdut.u_tdc_fine_layer.final_type180,refdut.u_tdc_fine_layer.final_type90,
     refdut.u_tdc_fine_layer.aux_rise_match,refdut.u_tdc_fine_layer.aux_fall_match,
     refdut.u_tdc_fine_layer.g_aux_4phase.rise_claimed_previous,refdut.u_tdc_fine_layer.g_aux_4phase.fall_claimed_previous,
     refdut.u_tdc_fine_layer.g_aux_4phase.rise_previous,refdut.u_tdc_fine_layer.g_aux_4phase.fall_previous})
     $fatal(1,"F候选或辅助事件归属不一致 time=%0t",$time);
 miter_cycles=miter_cycles+1;
end
always @(negedge dut.clk_100m) if(dut.rst_n_100m)
 if({dut.pulse_width_valid_100m,dut.pulse_width_ps_100m,dut.error_valid_100m,dut.error_code_100m} !==
    {refdut.pulse_width_valid_100m,refdut.pulse_width_ps_100m,refdut.error_valid_100m,refdut.error_code_100m})
    $fatal(1,"F的100MHz FIFO输出不一致 time=%0t",$time);
final $display("F_CYCLE_EQUIVALENCE_PASS cycles=%0d",miter_cycles);

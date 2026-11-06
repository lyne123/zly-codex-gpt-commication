`timescale 1ps/1ps
// 复用真实ILA的确认前包与有序采样记录，原RTL继续计算slot/归属/确认及后端流水。
module tb_replay;
reg sys_clk=0,sys_rst_n=0,pwm_in=0;
always #5000 sys_clk=~sys_clk;
`include "compensation_parameters.vh"
tdc_meas_top `COMPENSATION_PARAMETERS dut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
tdc_meas_top_reference `COMPENSATION_PARAMETERS refdut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
`include "miter_checks.svh"
reg [9:0] p0=0,p90=0,p180=0,p270=0;
reg [3:0] samples=0;
integer input_fd,output_fd,n,rc;
string input_file,output_file;
initial begin
 if(!$value$plusargs("INPUT=%s",input_file) || !$value$plusargs("OUTPUT=%s",output_file)) $fatal(1,"缺少复现文件参数");
 input_fd=$fopen(input_file,"r");output_fd=$fopen(output_file,"w");
 if(!input_fd || !output_fd) $fatal(1,"无法打开复现文件");
 $fdisplay(output_fd,"sample,rise_slots,fall_slots,fall_now,fall_previous,fall_claimed_previous,fall_match,final_types,sync_mask,edge_valid,edge_type,index,code,conflict,repeat_error,timestamp_valid,timestamp_type,timestamp_ps,width_valid,width_ps,error_valid,error_code");
 #100000 sys_rst_n=1;
 #500000;
 force dut.u_tdc_fine_layer.pack0_d1=p0;
 force dut.u_tdc_fine_layer.pack90_d2=p90;
 force dut.u_tdc_fine_layer.pack180_d1=p180;
 force dut.u_tdc_fine_layer.pack270_to90=p270;
 force dut.u_tdc_fine_layer.g_aux_4phase.ordered_samples=samples;
 force dut.u_tdc_fine_layer.g_aux_4phase.ordered_ready=1'b1;
 force dut.u_tdc_fine_layer.frame_ready=1'b1;
 force refdut.u_tdc_fine_layer.pack0_d1=p0;
 force refdut.u_tdc_fine_layer.pack90_d2=p90;
 force refdut.u_tdc_fine_layer.pack180_d1=p180;
 force refdut.u_tdc_fine_layer.pack270_to90=p270;
 force refdut.u_tdc_fine_layer.g_aux_4phase.ordered_samples=samples;
 force refdut.u_tdc_fine_layer.g_aux_4phase.ordered_ready=1'b1;
 force refdut.u_tdc_fine_layer.frame_ready=1'b1;
 while(!$feof(input_fd)) begin
  @(negedge dut.clk_500m);
  rc=$fscanf(input_fd,"%d %h %h %h %h %h\n",n,p0,p90,p180,p270,samples);
  if(rc==6) begin
   #999;
   $fdisplay(output_fd,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",n,
     dut.u_tdc_fine_layer.g_aux_4phase.aux_rise_slots,dut.u_tdc_fine_layer.g_aux_4phase.aux_fall_slots,
     dut.u_tdc_fine_layer.g_aux_4phase.fall_now,dut.u_tdc_fine_layer.g_aux_4phase.fall_previous,
     dut.u_tdc_fine_layer.g_aux_4phase.fall_claimed_previous,dut.u_tdc_fine_layer.aux_fall_match,
     {dut.u_tdc_fine_layer.final_type0,dut.u_tdc_fine_layer.final_type270,dut.u_tdc_fine_layer.final_type180,dut.u_tdc_fine_layer.final_type90},
     dut.sync_edge_valid,dut.edge_valid,dut.edge_type_q,dut.sel_index,dut.chosen_code,dut.polarity_conflict,dut.repeat_error,
     dut.timestamp_valid,dut.timestamp_edge_type,dut.timestamp_ps,dut.pulse_width_valid,dut.pulse_width_ps,dut.error_event_valid,dut.error_event_code);
  end else if(!$feof(input_fd)) $fatal(1,"真实复现输入格式错误");
 end
 $fclose(input_fd);$fclose(output_fd);$display("REAL_CSV_RTL_REPLAY_COMPLETE");$finish;
end
endmodule

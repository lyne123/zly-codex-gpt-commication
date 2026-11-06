`timescale 1ps/1ps
// 仅仿真强制候选接口，验证非零重复/孤立错误、越界细码拒收及粗计数回卷的流水对齐。
module tb_backend;
reg sys_clk=0,sys_rst_n=0,pwm_in=0;
always #5000 sys_clk=~sys_clk;
`include "compensation_parameters.vh"
tdc_meas_top `COMPENSATION_PARAMETERS dut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
tdc_meas_top_reference `COMPENSATION_PARAMETERS refdut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
`include "miter_pipe_checks.svh"
reg rv=0,nv=0,rt=0,nt=0;
reg [7:0] rcode=0,ncode=0;
reg [1:0] ri=0,ni=0;
integer cycle,c1=0,c2=0,c3=0,pairs=0;
reg wrap_started=0,wrap_finished=0;
initial begin
 #100000 sys_rst_n=1;#500000;
 force refdut.edge_valid=rv;force dut.edge_valid=nv;
 force refdut.edge_type_q=rt;force dut.edge_type_q=nt;
 force refdut.chosen_code=rcode;force dut.chosen_code=ncode;
 force refdut.sel_index=ri;force dut.sel_index=ni;
 force refdut.polarity_conflict=1'b0;force dut.polarity_conflict=1'b0;
 for(cycle=0;cycle<1200;cycle=cycle+1) begin
  @(negedge dut.clk_500m);
  nv=rv;nt=rt;ncode=rcode;ni=ri;rv=0;
  if(cycle==20 || cycle==45) begin rv=1;rt=1;rcode=13;ri=3;end
  if(cycle==65 || cycle==85) begin rv=1;rt=0;rcode=13;ri=3;end
  if(cycle==100) begin rv=1;rt=1;rcode=65;ri=3;end
  if(!wrap_started && cycle>200 && refdut.u_tdc_time_locate.coarse_counter==1016) begin
   rv=1;rt=1;rcode=13;ri=3;wrap_started=1;
  end
  if(wrap_started && !wrap_finished && refdut.u_tdc_time_locate.coarse_counter==4) begin
   rv=1;rt=0;rcode=13;ri=3;wrap_finished=1;
  end
 end
 @(negedge dut.clk_500m);nv=rv;nt=rt;ncode=rcode;ni=ri;rv=0;
 @(negedge dut.clk_500m);nv=0;
 #300000;
 if(c1!=1 || c2!=1 || c3!=0 || pairs!=2 || !wrap_finished) $fatal(1,"后端强制事件统计错误 R=%0d F=%0d RANGE=%0d PAIRS=%0d WRAP=%0d",c1,c2,c3,pairs,wrap_finished);
 $display("BACKEND_ERROR_WRAP_PASS repeat=1 orphan=1 range=0 pairs=2 wrap=1");$finish;
end
always @(negedge dut.clk_500m) if(dut.rst_n_500m) begin
 if(dut.error_event_valid) case(dut.error_event_code) 1:c1=c1+1;2:c2=c2+1;3:c3=c3+1;endcase
 if(dut.pulse_width_valid) pairs=pairs+1;
end
endmodule

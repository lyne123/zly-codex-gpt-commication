`timescale 1ps/1ps
// 独立全链路理想RTL验证；激励文件和参考边沿由各方案共同使用。
module tb_pwm;
reg sys_clk=0,sys_rst_n=0,pwm_in=0;
always #5000 sys_clk=~sys_clk;
`include "compensation_parameters.vh"
tdc_meas_top `COMPENSATION_PARAMETERS dut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
tdc_meas_top_reference `COMPENSATION_PARAMETERS refdut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
`include "miter_pipe_checks.svh"
string input_file,output_dir;
integer src,rc,id,tsfd,wfd,efd,cfd,epochfd,epoch_written=0;
time rise_ps,fall_ps;
initial begin
 if(!$value$plusargs("INPUT=%s",input_file) || !$value$plusargs("OUT=%s",output_dir)) $fatal(1,"缺少参数");
 src=$fopen(input_file,"r");tsfd=$fopen({output_dir,"/timestamps.csv"},"w");
 wfd=$fopen({output_dir,"/widths.csv"},"w");efd=$fopen({output_dir,"/errors.csv"},"w");
 cfd=$fopen({output_dir,"/candidate.csv"},"w");epochfd=$fopen({output_dir,"/epoch.csv"},"w");
 if(!src || !tsfd || !wfd || !efd || !cfd || !epochfd) $fatal(1,"文件打开失败");
 $fdisplay(tsfd,"time_ps,type,timestamp_ps");$fdisplay(wfd,"time_ps,width_ps");
 $fdisplay(efd,"time_ps,code");$fdisplay(cfd,"time_ps,type,index,code,conflict,repeat_error");$fdisplay(epochfd,"epoch_ps");
 #100000 sys_rst_n=1;
 while(!$feof(src)) begin
  rc=$fscanf(src,"%d %d %d\n",id,rise_ps,fall_ps);
  if(rc==3) begin
   if(rise_ps<$time || fall_ps<=rise_ps) $fatal(1,"非法边沿顺序");
   #(rise_ps-$time) pwm_in=1;
   #(fall_ps-$time) pwm_in=0;
  end else if(!$feof(src)) $fatal(1,"激励格式错误");
 end
 #300000;
 $display("PWM_RTL_COMPLETE overflow_result=%0d overflow_error=%0d",dut.result_fifo_overflow,dut.error_fifo_overflow);
 $fclose(src);$fclose(tsfd);$fclose(wfd);$fclose(efd);$fclose(cfd);$fclose(epochfd);$finish;
end
always @(negedge dut.clk_500m) if(dut.rst_n_500m && tsfd) begin
 if(!epoch_written) begin $fdisplay(epochfd,"%0d",$time-dut.u_tdc_time_locate.coarse_counter*2000+1000);epoch_written=1;end
 if(dut.edge_valid) $fdisplay(cfd,"%0t,%0d,%0d,%0d,%0d,%0d",$time,dut.edge_type_q,dut.sel_index,dut.chosen_code,dut.polarity_conflict,dut.repeat_error);
 if(dut.timestamp_valid) $fdisplay(tsfd,"%0t,%0d,%0d",$time,dut.timestamp_edge_type,dut.timestamp_ps);
 if(dut.pulse_width_valid) $fdisplay(wfd,"%0t,%0d",$time,dut.pulse_width_ps);
 if(dut.error_event_valid) $fdisplay(efd,"%0t,%0d",$time,dut.error_event_code);
end
endmodule

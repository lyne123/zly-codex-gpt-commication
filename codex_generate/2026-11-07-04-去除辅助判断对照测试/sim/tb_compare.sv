`timescale 1ps/1ps
// 三个完整顶层共享系统时钟、复位和冻结PWM；只读记录，不修改测量通路。
module tb_compare;
reg sys_clk=0,sys_rst_n=0,pwm_in=0;
always #5000 sys_clk=~sys_clk;
`define PARAMS_NOAUX #(.ENABLE_AUX_CONFIRM(0),.ENABLE_SKEW_COMP(1),.RISE_OFFSET_90_PS(18'sd36011),.FALL_OFFSET_90_PS(18'sd36011),.RISE_OFFSET_180_PS(18'sd35742),.FALL_OFFSET_180_PS(18'sd35742),.RISE_OFFSET_270_PS(18'sd35756),.FALL_OFFSET_270_PS(18'sd35756),.RISE_OFFSET_0_PS(18'sd36081),.FALL_OFFSET_0_PS(18'sd36081))
`define PARAMS_AUXON #(.ENABLE_AUX_CONFIRM(1),.ENABLE_SKEW_COMP(1),.RISE_OFFSET_90_PS(18'sd36011),.FALL_OFFSET_90_PS(18'sd36011),.RISE_OFFSET_180_PS(18'sd35742),.FALL_OFFSET_180_PS(18'sd35742),.RISE_OFFSET_270_PS(18'sd35756),.FALL_OFFSET_270_PS(18'sd35756),.RISE_OFFSET_0_PS(18'sd36081),.FALL_OFFSET_0_PS(18'sd36081))
`include "compensation_parameters.vh"
tdc_meas_top `PARAMS_NOAUX dut_noaux(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
tdc_meas_top `PARAMS_AUXON dut_aux(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
tdc_meas_top_reference `COMPENSATION_PARAMETERS refdut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
// 默认开关必须与指定提交同拍逐位一致；NoAux只允许极性/valid变化。
always @(negedge dut_aux.clk_500m) if($time>5000000) begin
 if({dut_aux.all_fine_code,dut_aux.sync_valid,dut_aux.sync_edge_valid,dut_aux.sync_edge_polarity,dut_aux.edge_valid,dut_aux.edge_type_q,dut_aux.chosen_code,dut_aux.sel_index,dut_aux.polarity_conflict,dut_aux.repeat_error,dut_aux.timestamp_valid,dut_aux.timestamp_ps,dut_aux.timestamp_edge_type,dut_aux.pulse_width_valid,dut_aux.pulse_width_ps,dut_aux.error_event_valid,dut_aux.error_event_code,dut_aux.result_fifo_overflow,dut_aux.error_fifo_overflow} !== {refdut.all_fine_code,refdut.sync_valid,refdut.sync_edge_valid,refdut.sync_edge_polarity,refdut.edge_valid,refdut.edge_type_q,refdut.chosen_code,refdut.sel_index,refdut.polarity_conflict,refdut.repeat_error,refdut.timestamp_valid,refdut.timestamp_ps,refdut.timestamp_edge_type,refdut.pulse_width_valid,refdut.pulse_width_ps,refdut.error_event_valid,refdut.error_event_code,refdut.result_fifo_overflow,refdut.error_fifo_overflow}) $fatal(1,"AUX_ON_BASELINE_MISMATCH time=%0t",$time);
 if({dut_aux.all_fine_code,dut_aux.sync_valid,dut_aux.u_tdc_time_locate.coarse_counter,dut_aux.u_tdc_time_locate.coarse_counter_d1} !== {dut_noaux.all_fine_code,dut_noaux.sync_valid,dut_noaux.u_tdc_time_locate.coarse_counter,dut_noaux.u_tdc_time_locate.coarse_counter_d1}) $fatal(1,"NOAUX_DATA_READY_COARSE_MISALIGN");
end
always @(negedge dut_aux.clk_100m) if($time>5000000)
 if({dut_aux.pulse_width_valid_100m,dut_aux.pulse_width_ps_100m,dut_aux.error_valid_100m,dut_aux.error_code_100m} !== {refdut.pulse_width_valid_100m,refdut.pulse_width_ps_100m,refdut.error_valid_100m,refdut.error_code_100m}) $fatal(1,"AUX_ON_FIFO_MISMATCH");
generate begin : OBS_aux_on
 string outdir;
 integer tsfd,wfd,efd,cfd,rawfd,fifofd,epochfd,errfifofd,diagfd,statfd,epoch_written=0;
 integer conflict_count=0,repeat_count=0,range_accepted=0,raw_multi=0;
 integer rr0=0,rr90=0,rr180=0,rr270=0;
 reg overflow_seen=0;
 integer phase,code_v,type_v;
 initial begin
  if(!$value$plusargs("OUT=%s",outdir)) $fatal(1,"缺少输出目录");
  tsfd=$fopen({outdir,"/aux_on/timestamps.csv"},"w");wfd=$fopen({outdir,"/aux_on/widths.csv"},"w");
  efd=$fopen({outdir,"/aux_on/errors.csv"},"w");cfd=$fopen({outdir,"/aux_on/candidate.csv"},"w");
  rawfd=$fopen({outdir,"/aux_on/raw.csv"},"w");fifofd=$fopen({outdir,"/aux_on/fifo.csv"},"w");
  epochfd=$fopen({outdir,"/aux_on/epoch.csv"},"w");errfifofd=$fopen({outdir,"/aux_on/error_fifo.csv"},"w");
  diagfd=$fopen({outdir,"/aux_on/diagnostics.csv"},"w");statfd=$fopen({outdir,"/aux_on/COUNTERS.json"},"w");
  if(!tsfd||!wfd||!efd||!cfd||!rawfd||!fifofd||!epochfd||!errfifofd||!diagfd||!statfd) $fatal(1,"观察文件打开失败");
  $fdisplay(tsfd,"time_ps,type,timestamp_ps");$fdisplay(wfd,"time_ps,width_ps");$fdisplay(efd,"time_ps,code");
  $fdisplay(cfd,"time_ps,coarse,type,index,code,conflict,repeat_error");$fdisplay(rawfd,"time_ps,mask,polarity,codes");
  $fdisplay(fifofd,"time_ps,width_ps");$fdisplay(errfifofd,"time_ps,code");$fdisplay(epochfd,"epoch_ps");$fdisplay(diagfd,"time_ps,kind,phase,code,type");
 end
 always @(negedge dut_aux.clk_500m) if(dut_aux.rst_n_500m && tsfd) begin
  if(!epoch_written) begin $fdisplay(epochfd,"%0d",$time-dut_aux.u_tdc_time_locate.coarse_counter*2000+1000);epoch_written=1;end
  if(dut_aux.sync_valid && |dut_aux.sync_edge_valid) begin
   $fdisplay(rawfd,"%0t,%0d,%0d,%0d",$time,dut_aux.sync_edge_valid,dut_aux.sync_edge_polarity,dut_aux.all_fine_code);
   if((dut_aux.sync_edge_valid & (dut_aux.sync_edge_valid-1))!=0) raw_multi=raw_multi+1;
   for(phase=0;phase<4;phase=phase+1) if(dut_aux.sync_edge_valid[phase]) begin
    code_v=(dut_aux.all_fine_code>>(phase*8))&255;type_v=(dut_aux.sync_edge_polarity>>(phase*2))&3;
    if(!((type_v==3 && code_v>=1 && code_v<=60)||(type_v==2 && code_v>=5 && code_v<=63))) begin
     range_accepted=range_accepted+1;$fdisplay(diagfd,"%0t,accepted_out_of_range,%0d,%0d,%0d",$time,phase,code_v,type_v);
    end
   end
  end
  if(dut_aux.edge_valid) $fdisplay(cfd,"%0t,%0d,%0d,%0d,%0d,%0d,%0d",$time,dut_aux.u_tdc_time_locate.coarse_counter_d1,dut_aux.edge_type_q,dut_aux.sel_index,dut_aux.chosen_code,dut_aux.polarity_conflict,dut_aux.repeat_error);
  if(dut_aux.timestamp_valid) $fdisplay(tsfd,"%0t,%0d,%0d",$time,dut_aux.timestamp_edge_type,dut_aux.timestamp_ps);
  if(dut_aux.pulse_width_valid) $fdisplay(wfd,"%0t,%0d",$time,dut_aux.pulse_width_ps);
  if(dut_aux.error_event_valid) $fdisplay(efd,"%0t,%0d",$time,dut_aux.error_event_code);
  if(dut_aux.polarity_conflict) begin conflict_count=conflict_count+1;$fdisplay(diagfd,"%0t,polarity_conflict,-1,-1,-1",$time);end
  if(dut_aux.repeat_error) begin repeat_count=repeat_count+1;$fdisplay(diagfd,"%0t,candidate_repeat,-1,-1,-1",$time);end
  if(dut_aux.result_fifo_overflow||dut_aux.error_fifo_overflow) overflow_seen=1;
 end
 always @(negedge dut_aux.clk_100m) if(dut_aux.rst_n_100m) begin
  if(dut_aux.pulse_width_valid_100m) $fdisplay(fifofd,"%0t,%0d",$time,dut_aux.pulse_width_ps_100m);
  if(dut_aux.error_valid_100m) $fdisplay(errfifofd,"%0t,%0d",$time,dut_aux.error_code_100m);
 end
 always @(negedge dut_aux.clk_500m) if(dut_aux.u_tdc_fine_layer.u_tdl0.encoder_ready && (dut_aux.u_tdc_fine_layer.u_tdl0.raw_edge_type==3 || dut_aux.u_tdc_fine_layer.u_tdl0.raw_edge_type==2) && !dut_aux.u_tdc_fine_layer.u_tdl0.code_in_range) rr0=rr0+1;
always @(negedge dut_aux.clk_500m_deg90) if(dut_aux.u_tdc_fine_layer.u_tdl90.encoder_ready && (dut_aux.u_tdc_fine_layer.u_tdl90.raw_edge_type==3 || dut_aux.u_tdc_fine_layer.u_tdl90.raw_edge_type==2) && !dut_aux.u_tdc_fine_layer.u_tdl90.code_in_range) rr90=rr90+1;
always @(negedge dut_aux.clk_500m_deg180) if(dut_aux.u_tdc_fine_layer.u_tdl180.encoder_ready && (dut_aux.u_tdc_fine_layer.u_tdl180.raw_edge_type==3 || dut_aux.u_tdc_fine_layer.u_tdl180.raw_edge_type==2) && !dut_aux.u_tdc_fine_layer.u_tdl180.code_in_range) rr180=rr180+1;
always @(negedge dut_aux.clk_500m_deg270) if(dut_aux.u_tdc_fine_layer.u_tdl270.encoder_ready && (dut_aux.u_tdc_fine_layer.u_tdl270.raw_edge_type==3 || dut_aux.u_tdc_fine_layer.u_tdl270.raw_edge_type==2) && !dut_aux.u_tdc_fine_layer.u_tdl270.code_in_range) rr270=rr270+1;
 task finish_report;
 begin
  $fdisplay(statfd,"{\"polarity_conflict\":%0d,\"candidate_repeat\":%0d,\"accepted_out_of_range\":%0d,\"raw_multiple_candidates\":%0d,\"raw_range_rejected\":%0d,\"FIFO_overflow_seen\":%0d}",conflict_count,repeat_count,range_accepted,raw_multi,rr0+rr90+rr180+rr270,overflow_seen);
  $fclose(tsfd);$fclose(wfd);$fclose(efd);$fclose(cfd);$fclose(rawfd);$fclose(fifofd);$fclose(epochfd);$fclose(errfifofd);$fclose(diagfd);$fclose(statfd);
 end
 endtask
end endgenerate
generate begin : OBS_noaux
 string outdir;
 integer tsfd,wfd,efd,cfd,rawfd,fifofd,epochfd,errfifofd,diagfd,statfd,epoch_written=0;
 integer conflict_count=0,repeat_count=0,range_accepted=0,raw_multi=0;
 integer rr0=0,rr90=0,rr180=0,rr270=0;
 reg overflow_seen=0;
 integer phase,code_v,type_v;
 initial begin
  if(!$value$plusargs("OUT=%s",outdir)) $fatal(1,"缺少输出目录");
  tsfd=$fopen({outdir,"/noaux/timestamps.csv"},"w");wfd=$fopen({outdir,"/noaux/widths.csv"},"w");
  efd=$fopen({outdir,"/noaux/errors.csv"},"w");cfd=$fopen({outdir,"/noaux/candidate.csv"},"w");
  rawfd=$fopen({outdir,"/noaux/raw.csv"},"w");fifofd=$fopen({outdir,"/noaux/fifo.csv"},"w");
  epochfd=$fopen({outdir,"/noaux/epoch.csv"},"w");errfifofd=$fopen({outdir,"/noaux/error_fifo.csv"},"w");
  diagfd=$fopen({outdir,"/noaux/diagnostics.csv"},"w");statfd=$fopen({outdir,"/noaux/COUNTERS.json"},"w");
  if(!tsfd||!wfd||!efd||!cfd||!rawfd||!fifofd||!epochfd||!errfifofd||!diagfd||!statfd) $fatal(1,"观察文件打开失败");
  $fdisplay(tsfd,"time_ps,type,timestamp_ps");$fdisplay(wfd,"time_ps,width_ps");$fdisplay(efd,"time_ps,code");
  $fdisplay(cfd,"time_ps,coarse,type,index,code,conflict,repeat_error");$fdisplay(rawfd,"time_ps,mask,polarity,codes");
  $fdisplay(fifofd,"time_ps,width_ps");$fdisplay(errfifofd,"time_ps,code");$fdisplay(epochfd,"epoch_ps");$fdisplay(diagfd,"time_ps,kind,phase,code,type");
 end
 always @(negedge dut_noaux.clk_500m) if(dut_noaux.rst_n_500m && tsfd) begin
  if(!epoch_written) begin $fdisplay(epochfd,"%0d",$time-dut_noaux.u_tdc_time_locate.coarse_counter*2000+1000);epoch_written=1;end
  if(dut_noaux.sync_valid && |dut_noaux.sync_edge_valid) begin
   $fdisplay(rawfd,"%0t,%0d,%0d,%0d",$time,dut_noaux.sync_edge_valid,dut_noaux.sync_edge_polarity,dut_noaux.all_fine_code);
   if((dut_noaux.sync_edge_valid & (dut_noaux.sync_edge_valid-1))!=0) raw_multi=raw_multi+1;
   for(phase=0;phase<4;phase=phase+1) if(dut_noaux.sync_edge_valid[phase]) begin
    code_v=(dut_noaux.all_fine_code>>(phase*8))&255;type_v=(dut_noaux.sync_edge_polarity>>(phase*2))&3;
    if(!((type_v==3 && code_v>=1 && code_v<=60)||(type_v==2 && code_v>=5 && code_v<=63))) begin
     range_accepted=range_accepted+1;$fdisplay(diagfd,"%0t,accepted_out_of_range,%0d,%0d,%0d",$time,phase,code_v,type_v);
    end
   end
  end
  if(dut_noaux.edge_valid) $fdisplay(cfd,"%0t,%0d,%0d,%0d,%0d,%0d,%0d",$time,dut_noaux.u_tdc_time_locate.coarse_counter_d1,dut_noaux.edge_type_q,dut_noaux.sel_index,dut_noaux.chosen_code,dut_noaux.polarity_conflict,dut_noaux.repeat_error);
  if(dut_noaux.timestamp_valid) $fdisplay(tsfd,"%0t,%0d,%0d",$time,dut_noaux.timestamp_edge_type,dut_noaux.timestamp_ps);
  if(dut_noaux.pulse_width_valid) $fdisplay(wfd,"%0t,%0d",$time,dut_noaux.pulse_width_ps);
  if(dut_noaux.error_event_valid) $fdisplay(efd,"%0t,%0d",$time,dut_noaux.error_event_code);
  if(dut_noaux.polarity_conflict) begin conflict_count=conflict_count+1;$fdisplay(diagfd,"%0t,polarity_conflict,-1,-1,-1",$time);end
  if(dut_noaux.repeat_error) begin repeat_count=repeat_count+1;$fdisplay(diagfd,"%0t,candidate_repeat,-1,-1,-1",$time);end
  if(dut_noaux.result_fifo_overflow||dut_noaux.error_fifo_overflow) overflow_seen=1;
 end
 always @(negedge dut_noaux.clk_100m) if(dut_noaux.rst_n_100m) begin
  if(dut_noaux.pulse_width_valid_100m) $fdisplay(fifofd,"%0t,%0d",$time,dut_noaux.pulse_width_ps_100m);
  if(dut_noaux.error_valid_100m) $fdisplay(errfifofd,"%0t,%0d",$time,dut_noaux.error_code_100m);
 end
 always @(negedge dut_noaux.clk_500m) if(dut_noaux.u_tdc_fine_layer.u_tdl0.encoder_ready && (dut_noaux.u_tdc_fine_layer.u_tdl0.raw_edge_type==3 || dut_noaux.u_tdc_fine_layer.u_tdl0.raw_edge_type==2) && !dut_noaux.u_tdc_fine_layer.u_tdl0.code_in_range) rr0=rr0+1;
always @(negedge dut_noaux.clk_500m_deg90) if(dut_noaux.u_tdc_fine_layer.u_tdl90.encoder_ready && (dut_noaux.u_tdc_fine_layer.u_tdl90.raw_edge_type==3 || dut_noaux.u_tdc_fine_layer.u_tdl90.raw_edge_type==2) && !dut_noaux.u_tdc_fine_layer.u_tdl90.code_in_range) rr90=rr90+1;
always @(negedge dut_noaux.clk_500m_deg180) if(dut_noaux.u_tdc_fine_layer.u_tdl180.encoder_ready && (dut_noaux.u_tdc_fine_layer.u_tdl180.raw_edge_type==3 || dut_noaux.u_tdc_fine_layer.u_tdl180.raw_edge_type==2) && !dut_noaux.u_tdc_fine_layer.u_tdl180.code_in_range) rr180=rr180+1;
always @(negedge dut_noaux.clk_500m_deg270) if(dut_noaux.u_tdc_fine_layer.u_tdl270.encoder_ready && (dut_noaux.u_tdc_fine_layer.u_tdl270.raw_edge_type==3 || dut_noaux.u_tdc_fine_layer.u_tdl270.raw_edge_type==2) && !dut_noaux.u_tdc_fine_layer.u_tdl270.code_in_range) rr270=rr270+1;
 task finish_report;
 begin
  $fdisplay(statfd,"{\"polarity_conflict\":%0d,\"candidate_repeat\":%0d,\"accepted_out_of_range\":%0d,\"raw_multiple_candidates\":%0d,\"raw_range_rejected\":%0d,\"FIFO_overflow_seen\":%0d}",conflict_count,repeat_count,range_accepted,raw_multi,rr0+rr90+rr180+rr270,overflow_seen);
  $fclose(tsfd);$fclose(wfd);$fclose(efd);$fclose(cfd);$fclose(rawfd);$fclose(fifofd);$fclose(epochfd);$fclose(errfifofd);$fclose(diagfd);$fclose(statfd);
 end
 endtask
end endgenerate
string input_file;
integer src,rc,id;
time rise_ps,fall_ps,period_ps;
initial begin
 if(!$value$plusargs("INPUT=%s",input_file)) $fatal(1,"缺少激励");
 src=$fopen(input_file,"r");if(!src) $fatal(1,"激励打开失败");
 #200000 sys_rst_n=1;
 while(!$feof(src)) begin
  rc=$fscanf(src,"%d %d %d %d",id,rise_ps,fall_ps,period_ps);
  if(rc==4) begin
   if(rise_ps<$time||fall_ps<=rise_ps) $fatal(1,"非法激励顺序");
   #(rise_ps-$time) pwm_in=1;#(fall_ps-$time) pwm_in=0;
  end else if(!$feof(src)) $fatal(1,"激励格式错误");
 end
 #500000;
 OBS_aux_on.finish_report();OBS_noaux.finish_report();
 $display("RTL_COMPARE_COMPLETE AUX_ON_BASE_CYCLE_EQUIVALENT=1 NOAUX_DATA_COARSE_ALIGNED=1");$finish;
end
initial begin #1000000000;$fatal(1,"RTL测试超时");end
endmodule

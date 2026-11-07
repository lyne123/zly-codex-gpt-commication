"""生成同一激励下的NoAux、AuxOn与冻结原版三个完整实例及只读观察。"""
from pathlib import Path
import shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_noaux_20261107_04'
base=(TASK/'sim/compensation_parameters.vh').read_text(encoding='utf-8').strip().split(' ',2)[2]
head='''`timescale 1ps/1ps
// 三个完整顶层共享系统时钟、复位和冻结PWM；只读记录，不修改测量通路。
module tb_compare;
reg sys_clk=0,sys_rst_n=0,pwm_in=0;
always #5000 sys_clk=~sys_clk;
'''
for name,value in [('NOAUX',0),('AUXON',1)]:head+=f'`define PARAMS_{name} '+base.replace('#(',f'#(.ENABLE_AUX_CONFIRM({value}),',1)+'\n'
head+='`include "compensation_parameters.vh"\n'
head+='tdc_meas_top `PARAMS_NOAUX dut_noaux(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));\n'
head+='tdc_meas_top `PARAMS_AUXON dut_aux(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));\n'
head+='tdc_meas_top_reference `COMPENSATION_PARAMETERS refdut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));\n'
signals=['all_fine_code','sync_valid','sync_edge_valid','sync_edge_polarity','edge_valid','edge_type_q','chosen_code','sel_index','polarity_conflict','repeat_error','timestamp_valid','timestamp_ps','timestamp_edge_type','pulse_width_valid','pulse_width_ps','error_event_valid','error_event_code','result_fifo_overflow','error_fifo_overflow']
bundle=lambda prefix,fields:'{'+','.join(prefix+'.'+s for s in fields)+'}'
head+=f'''// 默认开关必须与指定提交同拍逐位一致；NoAux只允许极性/valid变化。
always @(negedge dut_aux.clk_500m) if($time>5000000) begin
 if({bundle('dut_aux',signals)} !== {bundle('refdut',signals)}) $fatal(1,"AUX_ON_BASELINE_MISMATCH time=%0t",$time);
 if({bundle('dut_aux',['all_fine_code','sync_valid','u_tdc_time_locate.coarse_counter','u_tdc_time_locate.coarse_counter_d1'])} !== {bundle('dut_noaux',['all_fine_code','sync_valid','u_tdc_time_locate.coarse_counter','u_tdc_time_locate.coarse_counter_d1'])}) $fatal(1,"NOAUX_DATA_READY_COARSE_MISALIGN");
end
always @(negedge dut_aux.clk_100m) if($time>5000000)
 if({bundle('dut_aux',['pulse_width_valid_100m','pulse_width_ps_100m','error_valid_100m','error_code_100m'])} !== {bundle('refdut',['pulse_width_valid_100m','pulse_width_ps_100m','error_valid_100m','error_code_100m'])}) $fatal(1,"AUX_ON_FIFO_MISMATCH");
'''
observer=r'''generate begin : OBS_@NAME@
 string outdir;
 integer tsfd,wfd,efd,cfd,rawfd,fifofd,epochfd,errfifofd,diagfd,statfd,epoch_written=0;
 integer conflict_count=0,repeat_count=0,range_accepted=0,raw_multi=0;
 integer rr0=0,rr90=0,rr180=0,rr270=0;
 reg overflow_seen=0;
 integer phase,code_v,type_v;
 initial begin
  if(!$value$plusargs("OUT=%s",outdir)) $fatal(1,"缺少输出目录");
  tsfd=$fopen({outdir,"/@NAME@/timestamps.csv"},"w");wfd=$fopen({outdir,"/@NAME@/widths.csv"},"w");
  efd=$fopen({outdir,"/@NAME@/errors.csv"},"w");cfd=$fopen({outdir,"/@NAME@/candidate.csv"},"w");
  rawfd=$fopen({outdir,"/@NAME@/raw.csv"},"w");fifofd=$fopen({outdir,"/@NAME@/fifo.csv"},"w");
  epochfd=$fopen({outdir,"/@NAME@/epoch.csv"},"w");errfifofd=$fopen({outdir,"/@NAME@/error_fifo.csv"},"w");
  diagfd=$fopen({outdir,"/@NAME@/diagnostics.csv"},"w");statfd=$fopen({outdir,"/@NAME@/COUNTERS.json"},"w");
  if(!tsfd||!wfd||!efd||!cfd||!rawfd||!fifofd||!epochfd||!errfifofd||!diagfd||!statfd) $fatal(1,"观察文件打开失败");
  $fdisplay(tsfd,"time_ps,type,timestamp_ps");$fdisplay(wfd,"time_ps,width_ps");$fdisplay(efd,"time_ps,code");
  $fdisplay(cfd,"time_ps,coarse,type,index,code,conflict,repeat_error");$fdisplay(rawfd,"time_ps,mask,polarity,codes");
  $fdisplay(fifofd,"time_ps,width_ps");$fdisplay(errfifofd,"time_ps,code");$fdisplay(epochfd,"epoch_ps");$fdisplay(diagfd,"time_ps,kind,phase,code,type");
 end
 always @(negedge @DUT@.clk_500m) if(@DUT@.rst_n_500m && tsfd) begin
  if(!epoch_written) begin $fdisplay(epochfd,"%0d",$time-@DUT@.u_tdc_time_locate.coarse_counter*2000+1000);epoch_written=1;end
  if(@DUT@.sync_valid && |@DUT@.sync_edge_valid) begin
   $fdisplay(rawfd,"%0t,%0d,%0d,%0d",$time,@DUT@.sync_edge_valid,@DUT@.sync_edge_polarity,@DUT@.all_fine_code);
   if((@DUT@.sync_edge_valid & (@DUT@.sync_edge_valid-1))!=0) raw_multi=raw_multi+1;
   for(phase=0;phase<4;phase=phase+1) if(@DUT@.sync_edge_valid[phase]) begin
    code_v=(@DUT@.all_fine_code>>(phase*8))&255;type_v=(@DUT@.sync_edge_polarity>>(phase*2))&3;
    if(!((type_v==3 && code_v>=1 && code_v<=60)||(type_v==2 && code_v>=5 && code_v<=63))) begin
     range_accepted=range_accepted+1;$fdisplay(diagfd,"%0t,accepted_out_of_range,%0d,%0d,%0d",$time,phase,code_v,type_v);
    end
   end
  end
  if(@DUT@.edge_valid) $fdisplay(cfd,"%0t,%0d,%0d,%0d,%0d,%0d,%0d",$time,@DUT@.u_tdc_time_locate.coarse_counter_d1,@DUT@.edge_type_q,@DUT@.sel_index,@DUT@.chosen_code,@DUT@.polarity_conflict,@DUT@.repeat_error);
  if(@DUT@.timestamp_valid) $fdisplay(tsfd,"%0t,%0d,%0d",$time,@DUT@.timestamp_edge_type,@DUT@.timestamp_ps);
  if(@DUT@.pulse_width_valid) $fdisplay(wfd,"%0t,%0d",$time,@DUT@.pulse_width_ps);
  if(@DUT@.error_event_valid) $fdisplay(efd,"%0t,%0d",$time,@DUT@.error_event_code);
  if(@DUT@.polarity_conflict) begin conflict_count=conflict_count+1;$fdisplay(diagfd,"%0t,polarity_conflict,-1,-1,-1",$time);end
  if(@DUT@.repeat_error) begin repeat_count=repeat_count+1;$fdisplay(diagfd,"%0t,candidate_repeat,-1,-1,-1",$time);end
  if(@DUT@.result_fifo_overflow||@DUT@.error_fifo_overflow) overflow_seen=1;
 end
 always @(negedge @DUT@.clk_100m) if(@DUT@.rst_n_100m) begin
  if(@DUT@.pulse_width_valid_100m) $fdisplay(fifofd,"%0t,%0d",$time,@DUT@.pulse_width_ps_100m);
  if(@DUT@.error_valid_100m) $fdisplay(errfifofd,"%0t,%0d",$time,@DUT@.error_code_100m);
 end
 @RANGE_COUNTERS@
 task finish_report;
 begin
  $fdisplay(statfd,"{\"polarity_conflict\":%0d,\"candidate_repeat\":%0d,\"accepted_out_of_range\":%0d,\"raw_multiple_candidates\":%0d,\"raw_range_rejected\":%0d,\"FIFO_overflow_seen\":%0d}",conflict_count,repeat_count,range_accepted,raw_multi,rr0+rr90+rr180+rr270,overflow_seen);
  $fclose(tsfd);$fclose(wfd);$fclose(efd);$fclose(cfd);$fclose(rawfd);$fclose(fifofd);$fclose(epochfd);$fclose(errfifofd);$fclose(diagfd);$fclose(statfd);
 end
 endtask
end endgenerate
'''
for name,dut in [('aux_on','dut_aux'),('noaux','dut_noaux')]:
    counters=[]
    for phase,clock in [('0','clk_500m'),('90','clk_500m_deg90'),('180','clk_500m_deg180'),('270','clk_500m_deg270')]:
        enc=f'{dut}.u_tdc_fine_layer.u_tdl{phase}'
        counters.append(f'always @(negedge {dut}.{clock}) if({enc}.encoder_ready && ({enc}.raw_edge_type==3 || {enc}.raw_edge_type==2) && !{enc}.code_in_range) rr{phase}=rr{phase}+1;')
    head+=observer.replace('@NAME@',name).replace('@DUT@',dut).replace('@RANGE_COUNTERS@','\n'.join(counters))
head+='''string input_file;
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
'''
(TASK/'sim/tb_compare.sv').write_text(head,encoding='utf-8');shutil.copy2(TASK/'sim/tb_compare.sv',WORK/'sim/tb_compare.sv')
print('THREE_INSTANCE_RTL_BENCH_PREPARED')

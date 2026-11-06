"""冻结原3512激励及旧关联延迟；准备预先固定的112脉冲最小器件测试。"""
from pathlib import Path
import csv,hashlib,json,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
OLD=ROOT/'codex_generate/2026-11-05-06-四相TDC-MAX-SDF验证'
assert not (TASK/'inputs/SDF_INPUT_MANIFEST.json').exists(),'禁止覆盖SDF输入'
manifest={}
for name in ['full.txt','full_truth.csv','frozen_event_association.json']:
    src=OLD/'inputs'/name;dst=TASK/'inputs'/name;shutil.copy2(src,dst)
    manifest[name]=dict(source=str(src),sha256=hashlib.sha256(src.read_bytes()).hexdigest())
truth=[];t=5000000
for case in ['10M_50','20M_50','20M_5','20M_95','10M_20M_switch','adjacent_2ns','phase_boundary']:
    for phase in [1,499,1001,1999]:
        t=((t+1999)//2000)*2000+phase+200000
        for n in range(4):
            period,width={'10M_50':(100000,50000),'20M_50':(50000,25000),'20M_5':(50000,2500),
              '20M_95':(50000,47500),'adjacent_2ns':(4000,2000),'phase_boundary':(50000,[2499,2500,2501][n%3]),
              '10M_20M_switch':((100000,50000) if n%2==0 else (50000,25000))}[case]
            truth.append(dict(pulse_id=len(truth),case=case,rise_ps=t,fall_ps=t+width,true_width_ps=width,period_ps=period,phase_ps=phase));t+=period
with (TASK/'inputs/minimal.txt').open('w') as f:
    for r in truth:f.write(f"{r['pulse_id']} {r['rise_ps']} {r['fall_ps']} {r['period_ps']}\n")
with (TASK/'inputs/minimal_truth.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(truth[0]));w.writeheader();w.writerows(truth)
manifest['minimal']=dict(pulses=112,fixed_before_SDF=True,width_tolerance_ps=1000,scope='独立边界/短脉冲压力；非真实硬件状态再现')
(TASK/'inputs/SDF_INPUT_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
tb=(TASK/'sim/tb_sdf.sv').read_text(encoding='utf-8')
tb=tb.replace('integer src,rc,id,tsfd,wfd,efd,cfd,rawfd,fifofd,epochfd,epoch_written=0;','integer src,rc,id,tsfd,wfd,efd,cfd,rawfd,fifofd,epochfd,errfifofd,epoch_written=0;\nreg previous_emitted_valid=0,previous_emitted_type=0;')
tb=tb.replace('time rise_ps,fall_ps;','time rise_ps,fall_ps,period_ps;')
tb=tb.replace('"%d %d %d\\n",id,rise_ps,fall_ps','"%d %d %d %d\\n",id,rise_ps,fall_ps,period_ps').replace('if(rc==3)','if(rc==4)')
tb=tb.replace(' $fdisplay(efd,"time_ps,code");$fdisplay(cfd,"time_ps,type,index,code,conflict");',' $fdisplay(efd,"time_ps,code");$fdisplay(cfd,"time_ps,coarse,type,index,code,conflict,repeat_error");')
old=' if(dut.edge_valid) $fdisplay(cfd,"%0t,%0d,%0d,%0d,%0d",$time,dut.edge_type_q,dut.sel_index,dut.chosen_code,dut.polarity_conflict);'
new=''' if(dut.edge_valid) begin
  $fdisplay(cfd,"%0t,%0d,%0d,%0d,%0d,%0d,%0d",$time,dut.u_tdc_time_locate.coarse_counter,dut.edge_type_q,dut.sel_index,dut.chosen_code,dut.polarity_conflict,previous_emitted_valid && previous_emitted_type==dut.edge_type_q);
  if(previous_emitted_valid && previous_emitted_type==dut.edge_type_q) $fdisplay(efd,"%0t,103",$time);
  previous_emitted_valid=1;previous_emitted_type=dut.edge_type_q;
 end'''
assert tb.count(old)==1;tb=tb.replace(old,new)
tb=tb.replace(' rawfd=$fopen(',''' errfifofd=$fopen({output_dir,"/error_fifo.csv"},"w");$fdisplay(errfifofd,"time_ps,code");
 rawfd=$fopen(''')
tb=tb.replace(' $fclose(src);',' $fclose(errfifofd);$fclose(src);')
tb=tb.replace('initial begin #100000000;', '''always @(negedge dut.clk_100m) if(dut.rst_sync_100m[1] && errfifofd && dut.error_valid_100m)
 $fdisplay(errfifofd,"%0t,%0d",$time,dut.error_code_100m);
initial begin #1000000000;''')
(TASK/'sim/tb_sdf.sv').write_text(tb,encoding='utf-8')
print('SDF_INPUTS_FROZEN full=3512 minimal=112; not simulated')

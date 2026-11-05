"""从冻结输入生成短窗口和只读观察代码；不编辑正式 RTL 或实现文件。"""
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / '2026-11-05-01-四相TDC时序优化与连续测量验证'
SHIFT = 225280000
WINDOWS = [(238600000,238900000),(241900000,242200000),(245200000,245500000)]

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    work=ROOT/'build/short_baseline'
    work.mkdir(exist_ok=True)
    source=OLD/'results/optimized/baseline'
    assets=[source/'design.v',source/'design.sdf',OLD/'sim/stimuli/validation.txt',OLD/'sim/stimuli/validation_truth.csv']
    expected=['e4389019c08446f841f20c4feb9ce2be1966d0d19753a78b5977a9583dda9fd7','824f7490473fc2afe86341e23f04f64d14cb90b178dcc5223f621323df6adea1','451a2cb59cc0704a9e5ac8454bb983237543705f2c4782789b3067be4d9fa76f','780b31667267cd8560f5d879241c16e60203f5f348e474ba566a0a0b95bae3ac']
    for p,digest in zip(assets,expected):
        if sha(p)!=digest:raise ValueError(f'冻结输入 SHA256 不匹配，拒绝运行：{p}')
    formal=sorted((ROOT.parents[1]/'fpga_tdc_v3_cal_rtl').glob('*.v'))
    (ROOT/'inputs/SOURCE_SHA256.json').write_text(json.dumps({str(p):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in assets+formal},ensure_ascii=False,indent=2),encoding='utf-8')
    pulses=[list(map(int,l.split())) for l in assets[2].read_text().splitlines()]
    selected=[r for r in pulses if 237500000 <= r[1] <=245500000]
    (ROOT/'inputs/local_stimulus.txt').write_text(''.join(f'{i} {r-SHIFT} {f-SHIFT} {p}\n' for i,r,f,p in selected),encoding='ascii')
    with (ROOT/'inputs/EDGE_TIME_MAPPING.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['event_id','rise_absolute_ps','fall_absolute_ps','rise_local_ps','fall_local_ps','period_ps'])
        w.writerows([i,r,t,r-SHIFT,t-SHIFT,p] for i,r,t,p in selected)
    (ROOT/'inputs/SHORT_WINDOW.json').write_text(json.dumps(dict(shift_ps=SHIFT,clock_period_ps=2000,sys_clock_period_ps=10000,coarse_modulo_ps=2048000,windows_absolute_ps=WINDOWS,pulse_count=len(selected),first_original_rise_ps=selected[0][1],last_original_fall_ps=selected[-1][2]),indent=2),encoding='utf-8')
    text=assets[0].read_text(encoding='utf-8')
    modules=dict(re.findall(r'module\s+(\w+)\b(.*?)endmodule',text,re.S))
    fine=modules['tdc_fine_layer']
    def cell(body,name):
        m=re.search(r'(?<![\w\\])'+re.escape(name)+r'\s+\(\s*(.*?)\);',body,re.S)
        if not m: raise ValueError(f'网表中不存在单元 {name}')
        return dict(re.findall(r'\.(\w+)\(([^()]*)\)',m[1]))
    def pin(scope,name,port):
        return scope+'.'+name+(' ' if name.startswith('\\') else '')+'.'+port
    def concat(items): return '{'+','.join(items)+'}'
    scope='dut.u_tdc_fine_layer'
    fields=[];mapping=[];lines=['// 仅含层级读取及监测，不驱动 DUT。', 'integer observer_fd, capture_fd;']
    def add(name,width,expr,kind='physical',note=''):
        lines.append(f'wire [{width-1}:0] obs_{name} = {expr};')
        fields.append((name,width));mapping.append(dict(name=name,bits=width,expression=expr,kind=kind,note=note))
    for phase in [0,90,180,270]:
        inst=f'u_tdl{phase}'
        m=re.search(r'(tdc_phase_tdl_encoder\w*)\s+'+inst+r'\s*\(',fine)
        body=modules[m[1]];s=scope+'.'+inst;n=f'p{phase}_'
        add(n+'thermo',64,s+'.thermo_q')
        add(n+'carry',64,s+'.carry_tap')
        detects=[]
        for bit in [7,6]:
            cn=f'\\type_pipe_reg[{bit}]_srl4'
            if cn+'_srlopt' in body: cn+='_srlopt'
            cell(body,cn);detects.append(pin(s,cn,'D'))
        add(n+'detected_type',2,concat(detects),'mapped_pin','极性流水线第一存储单元的实际 D 端；包含布线延迟')
        raw=[];cq=[]
        for i in range(6,-1,-1):
            cn=f'\\code_q_reg[{i}]';ports=cell(body,cn)
            raw.append(s+'.'+ports['D'].strip()+(' ' if ports['D'].strip().startswith('\\') else ''))
            cq.append(pin(s,cn,'Q'))
        add(n+'code_raw',7,concat(raw),'mapped_net','code_q.D 的实际驱动网；计数树末级寄存器输出')
        add(n+'raw_edge_type',2,s+'.raw_edge_type')
        # 本工程外层参数为 60/5，覆盖编码器模块的 55/10 默认值。
        add(n+'code_in_range',1,f'((obs_{n}raw_edge_type==3 && obs_{n}code_raw>=1 && obs_{n}code_raw<=60) || (obs_{n}raw_edge_type==2 && obs_{n}code_raw>=5 && obs_{n}code_raw<64))','reconstructed','独立物理节点被 LUT 合并；按实际 60/5 参数重建，只作解释')
        cell(body,'output_ready_reg')
        add(n+'encoder_ready',1,pin(s,'output_ready_reg','D'),'mapped_pin','encoder_ready 对应 output_ready 的实际 D 端')
        add(n+'code_q',7,concat(cq),'mapped_pin')
        add(n+'edge_type_d',2,concat([pin(s,f'\\edge_type_q_reg[{i}]','D') for i in [1,0]]),'mapped_pin')
        add(n+'edge_type_q',2,concat([pin(s,f'\\edge_type_q_reg[{i}]','Q') for i in [1,0]]),'mapped_pin')
        add(n+'output_ready',1,pin(s,'output_ready_reg','Q'),'mapped_pin')
    for name in ['pwm_meta','pwm_sync','pwm_history','frame_ready','aux_up']:
        add(name,1,scope+'.'+name)
    for name in ['pwm_meta','pwm_sync','pwm_history']:
        for port in ['D','C','D_dly','C_dly','Q']:
            add(name+'_'+port,1,pin(scope,name+'_reg',port),'primitive_port' if '_dly' not in port else 'primitive_internal')
    for name in ['rise','fall']:
        srl=f'\\aux_{name}_pipe_reg[3]_srl4_u_tdl0_ready_pipe_reg_c_2'
        ff4=f'\\aux_{name}_pipe_reg[4]_u_tdl0_ready_pipe_reg_c_3'
        cell(fine,srl);cell(fine,ff4)
        add('aux_'+name,1,pin(scope,srl,'D'),'mapped_pin','边沿检测 LUT 输出，SRL 实际 D 端')
        bits=[pin(scope,f'\\aux_{name}_pipe_reg[{i}]','Q') for i in [6,5]]
        bits+=[pin(scope,ff4,'Q'),pin(scope,srl,'data')+'[3:0]']
        add('aux_'+name+'_pipe',7,concat(bits),'primitive_internal','bit0..3 读取 SRL16E 模型 data；bit4..6 读取物理 FF.Q；被优化掉的 bit7 未重建')
        add('aux_'+name+'_match',1,f'(|obs_aux_{name}_pipe[6:5])','reconstructed','物理组合 LUT 中的等价或表达式；最终确认另观测实际 FF.D')
    for pack in ['pack0_d1','pack90_d2','pack180_d1','pack270_to90']:
        bits=[]
        for i in range(9,-1,-1):
            if i==7:bits.append("1'b0")
            else:
                cn=f'\\{pack}_reg[{i}]';cell(fine,cn);bits.append(pin(scope,cn,'Q'))
        add(pack,10,concat(bits),'mapped_pin')
    for phase,index in [(90,0),(180,1),(270,2),(0,3)]:
        add(f'final_type{phase}',2,concat([pin(scope,f'\\sync_edge_polarity_reg[{index*2+i}]','D') for i in [1,0]]),'mapped_pin','最终确认/就绪门控后的实际寄存器 D 输入，包含物理延迟')
    for name,width in [('sync_edge_valid',4),('sync_edge_polarity',8),('sync_valid',1)]:add(name,width,'dut.'+name)
    lines += [
        'function automatic integer in_window(input time t);',
        'in_window = '+ ' || '.join(f'(t>={a} && t<={b})' for a,b in WINDOWS)+';','endfunction',
        'initial begin',
        'wait(output_dir!="");',
        'observer_fd=$fopen({output_dir,"/frontend_signals.csv"},"w");',
        '$fdisplay(observer_fd,"time_ps,local_time_ps,'+','.join(n for n,w in fields)+'");',
        'capture_fd=$fopen({output_dir,"/aux_capture.csv"},"w");',
        '$fdisplay(capture_fd,"time_ps,local_time_ps,stage,pin_D,effective_D,Q_before,pwm_in");','end',
        # 时钟半周期位置的稳定观察避免将时钟到 Q 过渡误判为错拍。
        'always @(negedge dut.clk_500m or negedge dut.clk_500m_deg90 or negedge dut.clk_500m_deg180 or negedge dut.clk_500m_deg270) begin',
        '#1;',
        'if(observer_fd && in_window($time+TIME_SHIFT))',
        '$fdisplay(observer_fd,"%0t,%0t,'+','.join('%h' if w>8 else '%0d' for n,w in fields)+'",$time+TIME_SHIFT,$time,'+','.join('obs_'+n for n,w in fields)+');','end']
    # 在模型实际采样时刻读取 D_dly，Q_before 保留前一状态。
    for stage in ['pwm_meta','pwm_sync','pwm_history']:
        lines += [f'always @(posedge obs_{stage}_C_dly) begin',
                  f'if(capture_fd && in_window($time+TIME_SHIFT)) $fdisplay(capture_fd,"%0t,%0t,{stage},%0d,%0d,%0d,%0d",$time+TIME_SHIFT,$time,obs_{stage}_D,obs_{stage}_D_dly,obs_{stage}_Q,pwm_in);','end']
    # 精确记录变化时间；逐信号日志仅覆盖三段窗口。
    lines += ['integer changes_fd;', 'initial begin wait(output_dir!=""); changes_fd=$fopen({output_dir,"/signal_changes.csv"},"w"); $fdisplay(changes_fd,"time_ps,local_time_ps,signal,value_hex"); end']
    for name,width in fields:
        lines += [f'always @(obs_{name}) if(changes_fd && in_window($time+TIME_SHIFT)) $fstrobe(changes_fd,"%0t,%0t,{name},%h",$time+TIME_SHIFT,$time,obs_{name});']
    observer='\n'.join(lines)+'\n'
    (ROOT/'sim/frontend_observer.svh').write_text(observer,encoding='utf-8')
    (ROOT/'inputs/SIGNAL_MAPPING.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
    tb=(OLD/'sim/tb_tdc.sv').read_text(encoding='utf-8')
    tb=tb.replace('module tb_tdc;','module tb_tdc;\n    localparam time TIME_SHIFT=225280000;')
    # 只平移日志时间和窗口判定，不改变输入驱动及任何被测逻辑。
    tb=tb.replace('$time>=238600000','$time+TIME_SHIFT>=238600000').replace('$time<=238900000','$time+TIME_SHIFT<=238900000')
    tb=tb.replace('$time>=241900000','$time+TIME_SHIFT>=241900000').replace('$time<=242200000','$time+TIME_SHIFT<=242200000')
    tb=tb.replace('$time>=245200000','$time+TIME_SHIFT>=245200000').replace('$time<=245500000','$time+TIME_SHIFT<=245500000')
    tb=tb.replace('",$time,','",$time+TIME_SHIFT,')
    tb=tb.replace('\nendmodule','\n`include "frontend_observer.svh"\nendmodule')
    (ROOT/'sim/tb_frontend.sv').write_text(tb,encoding='utf-8')
    for src,dst in [(assets[0],work/'design.v'),(assets[1],work/'design.sdf'),(OLD/'inputs/xsim.ini',work/'xsim.ini'),(ROOT/'sim/tb_frontend.sv',work/'input_tb.sv'),(ROOT/'sim/frontend_observer.svh',work/'frontend_observer.svh')]:shutil.copyfile(src,dst)
    (work/'compile.prj').write_text('verilog xil_defaultlib -d "GATE_NETLIST=" "design.v"\nsv xil_defaultlib -d "GATE_NETLIST=" -d "OPTIMIZED_GATE_NETLIST=" "input_tb.sv"\nnosort\n',encoding='ascii')
    viv='F:/Xilinx/Vivado/2022.2/bin'
    (work/'compile.bat').write_text(f'@echo off\ncall "{viv}/xvlog.bat" --incr --relax -L uvm -prj compile.prj -log xvlog.log\nif errorlevel 1 exit /b 1\ncall "{viv}/xelab.bat" --O3 --debug off --relax --mt 2 --maxdelay -L xil_defaultlib -L uvm -L simprims_ver -L secureip --snapshot measurement -transport_int_delays -pulse_r 0 -pulse_int_r 0 -pulse_e 0 -pulse_int_e 0 xil_defaultlib.tb_tdc xil_defaultlib.glbl -log elaborate.log\nexit /b %errorlevel%\n',encoding='ascii')
    out=ROOT/'results/short_baseline';out.mkdir(exist_ok=True)
    (work/'run_all.tcl').write_text('run all\nquit\n',encoding='ascii')
    (work/'run.bat').write_text(f'@echo off\ncall "{viv}/xsim.bat" measurement -tclbatch run_all.tcl -log "V:/results/short_baseline/simulation.log" -testplusarg "STIMULUS=V:/inputs/local_stimulus.txt" -testplusarg "OUTPUT_DIR=V:/results/short_baseline"\nexit /b %errorlevel%\n',encoding='ascii')
    print(f'准备完成：{len(selected)} 个原始脉冲，平移 {SHIFT} ps；观察点 {len(fields)} 个。')

if __name__=='__main__':main()

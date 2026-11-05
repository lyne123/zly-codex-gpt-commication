"""运行新Compensated完整MAX-SDF，保持全部时序检查。"""
from pathlib import Path
import argparse,csv,hashlib,json,re,shutil,subprocess

ROOT=Path('W:/');OLD=Path('U:/');DIAG=Path('V:/')
WINDOWS=[(238600000,238900000),(241900000,242200000),(245200000,245500000)]
SHIFT=225280000

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def execute(args,cwd,log):
    with log.open('wb') as f:subprocess.run(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,check=True)

def prepare():
    out=ROOT/'results/compensated';work=ROOT/'build/gate';work.mkdir(exist_ok=True)
    net=(out/'design.v').read_text(encoding='utf-8')
    modules=dict(re.findall(r'module\s+(\w+)\b(.*?)endmodule',net,re.S));fine=modules['tdc_fine_layer']
    scope='dut.u_tdc_fine_layer'
    def pin(name,port):
        m=re.search(re.escape(name)+r'\s+\(\s*(.*?)\);',fine,re.S)
        if not m or not re.search(r'\.'+port+r'\(',m[1]):raise ValueError(f'缺少实际观察单元/端口：{name}.{port}')
        return scope+'.'+name+(' ' if name.startswith('\\') else '')+'.'+port
    def vector(name,bits,port='Q'):
        return '{'+','.join(pin('\\'+name+f'[{i}]',port) for i in bits)+'}'
    fields=[];lines=['// 只读观察综合网表实际寄存器，不修改设计或时序模型。','integer gate_aux_fd,gate_window_fd,gate_capture_fd,gate_change_fd;']
    def add(name,width,expr):
        fields.append((name,width,expr));lines.append(f'wire [{width-1}:0] mon_{name}={expr};')
    add('rise_slots',4,vector('g_aux_4phase.aux_rise_slots_reg',range(3,-1,-1)))
    add('fall_slots',4,vector('g_aux_4phase.aux_fall_slots_reg',range(3,-1,-1)))
    # 已使用掩码bit0对后继帧无用途，综合已删除；只记录实际存在的bit3:1。
    add('rise_claim_3_1',3,vector('g_aux_4phase.rise_claimed_previous_reg',[3,2,1]))
    add('fall_claim_3_1',3,vector('g_aux_4phase.fall_claimed_previous_reg',[3,2,1]))
    for phase in range(4):
        for stage in ['meta','sync','history']:
            name=f'\\g_aux_4phase.g_phase[{phase}].pwm_{stage}_reg'
            add(f'p{phase*90}_{stage}',1,pin(name,'Q'))
            if stage=='meta':
                for port in ['D','C','D_dly','C_dly']:
                    # 端口D/C由网表校验，延迟输入为同版厂商原语的实际模型节点。
                    expression=pin(name,port if '_dly' not in port else port.replace('_dly',''))
                    if '_dly' in port:expression=expression+'_dly'
                    add(f'p{phase*90}_{port}',1,expression)
    for name in ['pack0_d1','pack90_d2','pack180_d1','pack270_to90']:
        add(name,10,'{'+','.join("1'b0" if i==7 else pin('\\'+name+f'_reg[{i}]','Q') for i in range(9,-1,-1))+'}')
    add('confirmed_type_D',8,vector('sync_edge_polarity_reg',range(7,-1,-1),'D'))
    add('raw_mask',4,'dut.sync_edge_valid');add('raw_polarity',8,'dut.sync_edge_polarity')
    condition=' || '.join(f'(t>={a} && t<={b})' for a,b in WINDOWS)
    lines+=['function automatic integer in_window(input time t); in_window='+condition+'; endfunction',
        'initial begin #1;',
        'gate_aux_fd=$fopen({output_dir,"/aux_events.csv"},"w");',
        'gate_window_fd=$fopen({output_dir,"/aux_windows.csv"},"w");',
        'gate_capture_fd=$fopen({output_dir,"/meta_capture.csv"},"w");',
        'gate_change_fd=$fopen({output_dir,"/meta_changes.csv"},"w");',
        '$fdisplay(gate_capture_fd,"time_ps,local_time_ps,phase,D,D_dly,Q_before,pwm_in");',
        '$fdisplay(gate_change_fd,"time_ps,local_time_ps,signal,value");']
    header='time_ps,local_time_ps,'+','.join(n for n,w,e in fields)
    for fd in ['gate_aux_fd','gate_window_fd']:lines.append(f'$fdisplay({fd},"{header}");')
    lines+=['end','always @(negedge dut.clk_500m) begin #1;','if($time>5000000 && gate_aux_fd) begin']
    fmt='%0t,%0t,'+','.join('%h' if w>8 else '%0d' for n,w,e in fields)
    args='$time+time_shift,$time,'+','.join('mon_'+n for n,w,e in fields)
    lines += [f'if((|mon_rise_slots)||(|mon_fall_slots)||(|mon_raw_mask)) $fdisplay(gate_aux_fd,"{fmt}",{args});',f'if(in_window($time+time_shift)) $fdisplay(gate_window_fd,"{fmt}",{args});','end end']
    for phase in range(4):
        ph=phase*90
        lines += [f'always @(posedge mon_p{ph}_C_dly) if(gate_capture_fd && in_window($time+time_shift)) $fdisplay(gate_capture_fd,"%0t,%0t,{ph},%0d,%0d,%0d,%0d",$time+time_shift,$time,mon_p{ph}_D,mon_p{ph}_D_dly,mon_p{ph}_meta,pwm_in);']
        for signal in [f'p{ph}_D',f'p{ph}_D_dly',f'p{ph}_C_dly',f'p{ph}_meta',f'p{ph}_sync',f'p{ph}_history']:
            lines.append(f'always @(mon_{signal}) if(gate_change_fd && in_window($time+time_shift)) $fstrobe(gate_change_fd,"%0t,%0t,{signal},%0d",$time+time_shift,$time,mon_{signal});')
    (ROOT/'sim/gate_observer.svh').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (ROOT/'inputs/GATE_SIGNAL_MAPPING.json').write_text(json.dumps([dict(name=n,bits=w,expression=e) for n,w,e in fields],indent=2),encoding='utf-8')
    tb=(OLD/'sim/tb_tdc.sv').read_text(encoding='utf-8')
    tb=tb.replace('module tb_tdc;','module tb_tdc;\n    time time_shift=0;\n    initial if($value$plusargs("TIME_SHIFT=%d",time_shift)) begin end')
    # 只平移日志时间；驱动仍严格使用输入文件中的本地绝对边沿时间。
    tb=re.sub(r'(\$fdisplay\([^\n]*?)\$time',r'\1($time+time_shift)',tb)
    tb=tb.replace('$fdisplay(epoch_fd,"%0d",($time+time_shift)-monitor_coarse*2000+1000);','$fdisplay(epoch_fd,"%0d",$time-monitor_coarse*2000+1000);')
    for lo,hi in WINDOWS:
        tb=tb.replace(f'$time>={lo}',f'$time+time_shift>={lo}').replace(f'$time<={hi}',f'$time+time_shift<={hi}')
    tb=tb.replace('\nendmodule','\n`include "gate_observer.svh"\nendmodule')
    (ROOT/'sim/tb_gate.sv').write_text(tb,encoding='utf-8')
    for src,dst in [(out/'design.v',work/'design.v'),(out/'design.sdf',work/'design.sdf'),(OLD/'inputs/xsim.ini',work/'xsim.ini'),(ROOT/'sim/tb_gate.sv',work/'input_tb.sv'),(ROOT/'sim/gate_observer.svh',work/'gate_observer.svh')]:shutil.copyfile(src,dst)
    (work/'compile.prj').write_text('verilog xil_defaultlib -d "GATE_NETLIST=" "design.v"\nsv xil_defaultlib -d "GATE_NETLIST=" -d "OPTIMIZED_GATE_NETLIST=" "input_tb.sv"\nnosort\n',encoding='ascii')
    viv='F:/Xilinx/Vivado/2022.2/bin'
    (work/'compile.bat').write_text(f'@echo off\ncall "{viv}/xvlog.bat" --incr --relax -L uvm -prj compile.prj -log xvlog.log\nif errorlevel 1 exit /b 1\ncall "{viv}/xelab.bat" --O3 --debug off --relax --mt 2 --maxdelay -L xil_defaultlib -L uvm -L simprims_ver -L secureip --snapshot measurement -transport_int_delays -pulse_r 0 -pulse_int_r 0 -pulse_e 0 -pulse_int_e 0 xil_defaultlib.tb_tdc xil_defaultlib.glbl -log elaborate.log\nexit /b %errorlevel%\n',encoding='ascii')
    (work/'run_all.tcl').write_text('run all\nquit\n',encoding='ascii')
    shutil.copyfile(OLD/'results/calibration/optimized/baseline/gate/metadata.json',ROOT/'inputs/frozen_baseline_association.json')
    metadata=dict(netlist_sha256=sha(out/'design.v'),sdf_sha256=sha(out/'design.sdf'),dcp_sha256=sha(out/'design.dcp'),tb_sha256=sha(ROOT/'sim/tb_gate.sv'),observer_sha256=sha(ROOT/'sim/gate_observer.svh'),timing_checks='enabled',corner='slow/MAX',tool='XSim 2022.2')
    (ROOT/'inputs/GATE_BUILD_MANIFEST.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8');print('GATE_PREPARED',len(fields),'physical observations')

def run(dataset):
    parent=ROOT/'results/compensated';case=parent/('gate_'+dataset)
    if case.exists():raise SystemExit(f'禁止覆盖已有SDF证据：{case}')
    if dataset=='full':
        s=json.loads((ROOT/'results/TIMING_REVIEW.json').read_text())
        assert s['main_static_pass'],'核心静态时序未通过，停止后续依赖步骤'
    case.mkdir();shift=SHIFT if dataset=='local' else 0
    if dataset=='local':
        shutil.copyfile(DIAG/'inputs/local_stimulus.txt',case/'stimulus.txt')
        ids=[int(line.split()[0]) for line in (case/'stimulus.txt').read_text().splitlines()]
        full={int(r['pulse_id']):r for r in read(OLD/'sim/stimuli/validation_truth.csv')}
        rows=[]
        for i,pid in enumerate(ids):
            row=dict(full[pid]);row['source_event_id']=pid;row['pulse_id']=i;rows.append(row)
        write(case/'truth.csv',rows)
    else:
        shutil.copyfile(OLD/'sim/stimuli/validation.txt',case/'stimulus.txt')
        shutil.copyfile(OLD/'sim/stimuli/validation_truth.csv',case/'truth.csv')
    work=ROOT/'build/gate';viv='F:/Xilinx/Vivado/2022.2/bin'
    script=f'@echo off\ncall "{viv}/xsim.bat" measurement -tclbatch run_all.tcl -log "{case.as_posix()}/simulation.log" -testplusarg "STIMULUS={case.as_posix()}/stimulus.txt" -testplusarg "OUTPUT_DIR={case.as_posix()}" -testplusarg "TIME_SHIFT={shift}"\nexit /b %errorlevel%\n'
    (case/'run.bat').write_text(script,encoding='ascii')
    execute(['cmd.exe','/d','/c',str(case/'run.bat')],work,case/'console.log')
    with (case/'simulation.log').open('rb') as f:f.seek(max(0,(case/'simulation.log').stat().st_size-8192));tail=f.read()
    if b'TDC_SIM_DONE' not in tail:raise RuntimeError('SDF仿真未正常结束')
    shutil.copyfile(work/'elaborate.log',case/'elaboration.log')
    (case/'run_manifest.txt').write_text(f'level=gate\nvariant=compensated\ndataset={dataset}\ntime_shift_ps={shift}\ntiming_checks=enabled\ncorner=slow/MAX\n',encoding='ascii')
    print('GATE_RUN_DONE',dataset,flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','compile','local','full']);a=p.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='compile':execute(['cmd.exe','/d','/c','compile.bat'],ROOT/'build/gate',ROOT/'logs/gate_compile_console.log')
    else:run(a.action)

if __name__=='__main__':main()

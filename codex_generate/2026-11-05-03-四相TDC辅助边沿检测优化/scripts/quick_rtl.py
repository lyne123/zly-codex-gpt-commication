"""复用原测试平台及理想模型，快速验证边沿、归属和脉宽；不运行 Vivado。"""
from pathlib import Path
import argparse,bisect,csv,difflib,hashlib,json,math,shutil,statistics,subprocess

TASK=Path(__file__).resolve().parents[1]
ROOT=Path('W:/')
OLD=TASK.parent/'2026-11-05-01-四相TDC时序优化与连续测量验证'
DIAG=TASK.parent/'2026-11-05-02-四相TDC前端丢沿定位'
MOD=2048000

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def prepare():
    formal=TASK.parents[1]/'fpga_tdc_v3_cal_rtl'
    for p in formal.glob('*.v'):shutil.copyfile(p,ROOT/'rtl'/p.name)
    before=(ROOT/'original/rtl/tdc_fine_layer.v').read_text(encoding='utf-8')
    after=(ROOT/'rtl/tdc_fine_layer.v').read_text(encoding='utf-8')
    assert before[before.index('module tdc_phase_tdl_encoder'):]==after[after.index('module tdc_phase_tdl_encoder'):]
    assert before[before.index('    // 1. 主测量通路'):before.index('    // 4. 辅助通路')]==after[after.index('    // 1. 主测量通路'):after.index('    // 4. 辅助通路')]
    for p in (ROOT/'original/rtl').glob('*.v'):
        if p.name!='tdc_fine_layer.v':assert sha(p)==sha(formal/p.name),p.name
    (ROOT/'RTL.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='original/tdc_fine_layer.v',tofile='rtl/tdc_fine_layer.v')),encoding='utf-8')
    (ROOT/'inputs/SOURCE_SHA256.json').write_text(json.dumps({p.name:dict(original=sha(ROOT/'original/rtl'/p.name),modified=sha(p)) for p in (ROOT/'rtl').glob('*.v')},indent=2),encoding='utf-8')
    tb=(OLD/'sim/tb_tdc.sv').read_text(encoding='utf-8')
    tb=tb.replace('    string stimulus, output_dir, sdf_file;', '''`ifdef AUX_MODE
    defparam dut.u_tdc_fine_layer.ENABLE_AUX_4PHASE=`AUX_MODE;
`endif
`ifndef GATE_NETLIST
    // 仅测试平台注入辅助输入路径延迟，顶层真实输入及真值文件不变。
    integer aux_input_delay=0;
    reg delayed_aux=0;
    // 延迟非阻塞赋值保留每条输入转换，避免惯性延迟错误过滤短脉冲。
    always @(pwm_in) delayed_aux <= #(aux_input_delay) pwm_in;
    initial begin
        if ($value$plusargs("AUX_INPUT_DELAY_PS=%d",aux_input_delay)) begin end
        force dut.u_tdc_fine_layer.pwm_aux_in=delayed_aux;
    end
    integer input_rises=0,input_falls=0,transport_rises=0,transport_falls=0;
    integer tdl_rises=0,tdl_falls=0,path_fd;
    // 输入从10us以后开始，计数从5us开始排除模型上电X→0初始化。
    always @(posedge pwm_in) if($time>5000000) input_rises=input_rises+1;
    always @(negedge pwm_in) if($time>5000000) input_falls=input_falls+1;
    always @(posedge delayed_aux) if($time>5000000) transport_rises=transport_rises+1;
    always @(negedge delayed_aux) if($time>5000000) transport_falls=transport_falls+1;
    always @(posedge dut.u_tdc_fine_layer.pwm_tdl[0]) if($time>5000000) tdl_rises=tdl_rises+1;
    always @(negedge dut.u_tdc_fine_layer.pwm_tdl[0]) if($time>5000000) tdl_falls=tdl_falls+1;
`endif
    string stimulus, output_dir, sdf_file;''')
    tb=tb.replace('        $display("TDC_SIM_DONE time_ps=%0t",$time);','''`ifndef GATE_NETLIST
        path_fd=$fopen({output_dir,"/PATH_EDGE_COUNTS.csv"},"w");
        $fdisplay(path_fd,"input_rises,input_falls,aux_path_rises,aux_path_falls,tdl0_path_rises,tdl0_path_falls");
        $fdisplay(path_fd,"%0d,%0d,%0d,%0d,%0d,%0d",input_rises,input_falls,transport_rises,transport_falls,tdl_rises,tdl_falls);
        $fclose(path_fd);
        if(input_rises!=transport_rises || input_falls!=transport_falls || input_rises!=tdl_rises || input_falls!=tdl_falls)
            $fatal(1,"测试平台路径模型丢失了输入转换");
`endif
        $display("TDC_SIM_DONE time_ps=%0t",$time);''')
    tb=tb.replace('\nendmodule','\n`ifdef AUX_MODE\n`include "aux_monitor.svh"\n`endif\nendmodule')
    (ROOT/'sim/tb_quick.sv').write_text(tb,encoding='utf-8')
    models=(OLD/'sim/functional_models.v').read_text(encoding='utf-8')
    models=models.replace('    assign O=INIT[I0];','''`ifndef RTL_LUT_DELAY
`define RTL_LUT_DELAY 0
`endif
    // 路径应力使用传输延迟；默认0保持上一轮理想模型。
    generate if (`RTL_LUT_DELAY==0) begin
        assign O=INIT[I0];
    end else begin
        reg transported;
        initial begin #0; transported <= #(`RTL_LUT_DELAY) INIT[I0]; end
        always @(I0) transported <= #(`RTL_LUT_DELAY) INIT[I0];
        assign O=transported;
    end endgenerate''')
    (ROOT/'sim/functional_models.v').write_text(models,encoding='utf-8')
    monitor='''// 只读记录辅助事件位置、跨相位采样与每相确认结果。
integer aux_fd;
initial begin
    #1;
    aux_fd=$fopen({output_dir,"/aux_trace.csv"},"w");
    $fdisplay(aux_fd,"time_ps,rise_slots,fall_slots,samples,armed,rise_match,fall_match,pack0,pack90,pack180,pack270,final0,final90,final180,final270");
end
`if `AUX_MODE
always @(negedge dut.clk_500m) if(aux_fd && $time>5000000)
    $fdisplay(aux_fd,"%0t,%0d,%0d,%0d,%0d,%0d,%0d,%h,%h,%h,%h,%0d,%0d,%0d,%0d",$time,
        dut.u_tdc_fine_layer.g_aux_4phase.aux_rise_slots,dut.u_tdc_fine_layer.g_aux_4phase.aux_fall_slots,
        dut.u_tdc_fine_layer.g_aux_4phase.ordered_samples,dut.u_tdc_fine_layer.g_aux_4phase.armed,
        dut.u_tdc_fine_layer.aux_rise_match,dut.u_tdc_fine_layer.aux_fall_match,
        dut.u_tdc_fine_layer.pack0_d1,dut.u_tdc_fine_layer.pack90_d2,dut.u_tdc_fine_layer.pack180_d1,dut.u_tdc_fine_layer.pack270_to90,
        dut.u_tdc_fine_layer.final_type0,dut.u_tdc_fine_layer.final_type90,dut.u_tdc_fine_layer.final_type180,dut.u_tdc_fine_layer.final_type270);
`endif
'''.replace('`if `AUX_MODE','`ifdef FOUR_PHASE_MONITOR')
    (ROOT/'sim/aux_monitor.svh').write_text(monitor,encoding='utf-8')
    stimuli=ROOT/'sim/stimuli';stimuli.mkdir(exist_ok=True)
    phases=[0,1,249,499,500,501,749,999,1000,1001,1249,1499,1500,1501,1749,1999]
    for name,width,period,burst in [('fixed253',25300,50000,4),('pwm20_5',2500,50000,4),('pwm20_95',47500,50000,4),('pwm20_50',25000,50000,4),('high1ns',1000,50000,1),('low1ns',49000,50000,4),('high_low1ns',1000,2000,2),('high2ns',2000,50000,2),('low2ns',48000,50000,2),('high_low2ns',2000,4000,2)]:
        rows=[]
        scan=sorted(set(range(0,2000,20))|set(phases)) if '2ns' in name else phases
        for block,phase in enumerate(scan):
            start=10000000+block*400000+phase
            for k in range(burst):
                r=start+k*period
                rows.append(dict(pulse_id=len(rows),case=name,rise_ps=r,fall_ps=r+width,period_ps=period,true_width_ps=width,phase_ps=r%2000))
        write(stimuli/(name+'_truth.csv'),rows)
        (stimuli/(name+'.txt')).write_text(''.join(f"{r['pulse_id']} {r['rise_ps']} {r['fall_ps']} {r['period_ps']}\n" for r in rows),encoding='ascii')
    shutil.copyfile(DIAG/'inputs/local_stimulus.txt',stimuli/'local.txt')
    previous={int(r['pulse_id']):r for r in read(OLD/'sim/stimuli/validation_truth.csv')}
    local=[]
    for line in (stimuli/'local.txt').read_text().splitlines():
        i,r,f,p=map(int,line.split());local.append(dict(pulse_id=i,case='local',rise_ps=r,fall_ps=f,period_ps=p,true_width_ps=f-r,phase_ps=r%2000))
    write(stimuli/'local_truth.csv',local)
    shutil.copyfile(OLD/'sim/stimuli/validation.txt',stimuli/'full.txt')
    shutil.copyfile(OLD/'sim/stimuli/validation_truth.csv',stimuli/'full_truth.csv')
    index=TASK.parent/'README.md';data=index.read_bytes()
    if TASK.name.encode() not in data:
        eol=b'\r\n' if b'\r\n' in data else b'\n'
        row=f'| 2026-11-05-03 | [四相TDC辅助边沿检测优化]({TASK.name}/RESULTS.md) |'.encode('utf-8')
        pos=data.index(b'\n',data.index(b'| 2026-11-05-02 |'))+1
        index.write_bytes(data[:pos]+row+eol+data[pos:])

def analyze(case,model_delay):
    truth=read(case/'truth.csv');timestamps=read(case/'timestamps.csv');widths=read(case/'widths.csv');errors=read(case/'errors.csv')
    epoch=int(read(case/'clock_epoch.csv')[0]['epoch_ps'])
    bypol={p:sorted((int(r['rise_ps' if p else 'fall_ps']),int(r['pulse_id'])) for r in truth) for p in [0,1]}
    counts={p:{} for p in [0,1]};associated=[];ambiguous=[]
    for t in timestamps:
        p=int(t['type']);emit=int(t['time_ps'])
        # 32000ps来自上一轮冻结理想RTL的公共流水线偏移，不重新拟合验证集。
        wrapped=(int(t['timestamp_ps'])-32000-model_delay+epoch)%MOD
        estimate=wrapped+round((emit-40000-wrapped)/MOD)*MOD
        options=bypol[p];times=[x[0] for x in options];at=bisect.bisect_left(times,estimate)
        near=[j for j in [at-1,at] if 0<=j<len(options)];j=min(near,key=lambda k:abs(options[k][0]-estimate))
        true,pulse=options[j];residual=estimate-true
        if abs(residual)>20:ambiguous.append(dict(type=p,estimated_ps=estimate,nearest_id=pulse,residual_ps=residual))
        counts[p][pulse]=counts[p].get(pulse,0)+1
        associated.append(dict(pulse_id=pulse,type=p,estimated_ps=estimate,true_ps=true,residual_ps=residual))
    pairs=[];pending=None
    for e in associated:
        if e['type']:pending=e
        elif pending:pairs.append((pending,e));pending=None
    measurements=[];truth_byid={int(r['pulse_id']):r for r in truth}
    for (r,f),w in zip(pairs,widths):
        target=truth_byid[f['pulse_id']];measurements.append(dict(rise_id=r['pulse_id'],fall_id=f['pulse_id'],matched=int(r['pulse_id']==f['pulse_id']),measured_ps=int(w['width_ps']),true_ps=int(target['true_width_ps']),error_ps=int(w['width_ps'])-int(target['true_width_ps'])))
    missing={p:[int(r['pulse_id']) for r in truth if not counts[p].get(int(r['pulse_id']))] for p in [0,1]}
    duplicates={p:[i for i,n in counts[p].items() if n>1] for p in [0,1]}
    vals=[r['error_ps'] for r in measurements if r['matched']]
    auxfile=case/'aux_trace.csv'
    if not auxfile.exists():auxfile=case/'aux.csv'
    aux=read(auxfile) if auxfile.exists() else []
    aux_count={p:sum(int(r[key]).bit_count() for r in aux) for p,key in [(1,'rise_slots'),(0,'fall_slots')]}
    matched=sum(r['matched'] for r in measurements)
    result=dict(expected_pulses=len(truth),actual_edges=len(timestamps),expected_edges=2*len(truth),missing_rise=missing[1],missing_fall=missing[0],duplicates=duplicates,mispairs=len(measurements)-matched,correct_widths=matched,output_widths=len(widths),errors=errors,association_faults=ambiguous,aux_rises=aux_count[1],aux_falls=aux_count[0],rmse_ps=math.sqrt(statistics.mean(v*v for v in vals)) if vals else None,bias_ps=statistics.mean(vals) if vals else None,std_ps=statistics.pstdev(vals) if vals else None)
    result['pass_measurement']=len(timestamps)==2*len(truth) and matched==len(truth) and not any(missing.values()) and not any(duplicates.values()) and not errors and not ambiguous
    result['pass_aux']=aux_count[1]==aux_count[0]==len(truth) if aux else None
    (case/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if associated:write(case/'associated.csv',associated)
    if measurements:write(case/'measurements.csv',measurements)
    print(case.name,json.dumps({k:result[k] for k in ['expected_pulses','actual_edges','correct_widths','mispairs','pass_measurement','pass_aux','rmse_ps']},ensure_ascii=False),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--mode',type=int,choices=[0,1],default=1);p.add_argument('--lut-delay',type=int,default=0);p.add_argument('--aux-delay',type=int,default=0);p.add_argument('--run-tag',default='r4');p.add_argument('--cases',nargs='+',default=['local','fixed253','pwm20_5','pwm20_95','pwm20_50','high2ns','low2ns','high_low2ns']);a=p.parse_args()
    if a.prepare:prepare();return
    work=ROOT/'build'/f'rtl_a{a.mode}_l{a.lut_delay}_{a.run_tag}';work.mkdir(exist_ok=True)
    command=['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_tdc','-I',str(ROOT/'sim'),f'-DAUX_MODE={a.mode}',f'-DRTL_LUT_DELAY={a.lut_delay}']
    if a.mode:command+=['-DFOUR_PHASE_MONITOR']
    command+=['-o',str(work/'sim.vvp'),str(ROOT/'sim/tb_quick.sv'),str(ROOT/'sim/functional_models.v')]+[str(f) for f in sorted((ROOT/'rtl').glob('*.v'))]
    with (work/'compile.log').open('wb') as log:subprocess.run(command,cwd=work,stdout=log,stderr=subprocess.STDOUT,check=True)
    for name in a.cases:
        case=ROOT/'results'/f'rtl_a{a.mode}_l{a.lut_delay}_d{a.aux_delay}_{name}_{a.run_tag}'
        if case.exists():raise SystemExit(f'禁止覆盖已运行的证据：{case}')
        case.mkdir()
        for src,dest in [(ROOT/'sim/stimuli'/(name+'.txt'),'stimulus.txt'),(ROOT/'sim/stimuli'/(name+'_truth.csv'),'truth.csv')]:shutil.copyfile(src,case/dest)
        manifest=dict(mode=a.mode,lut_delay_ps=a.lut_delay,aux_delay_ps=a.aux_delay,delay_model='transport',rtl_sha256={f.name:sha(f) for f in sorted((ROOT/'rtl').glob('*.v'))},tb_sha256=sha(ROOT/'sim/tb_quick.sv'),model_sha256=sha(ROOT/'sim/functional_models.v'),stimulus_sha256=sha(case/'stimulus.txt'))
        (case/'INPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        args=['F:/iverilog/bin/vvp.exe',str(work/'sim.vvp'),f'+STIMULUS={case.as_posix()}/stimulus.txt',f'+OUTPUT_DIR={case.as_posix()}',f'+AUX_INPUT_DELAY_PS={a.aux_delay}']
        with (case/'simulation.log').open('wb') as log:subprocess.run(args,cwd=work,stdout=log,stderr=subprocess.STDOUT,check=True)
        data=(case/'simulation.log').read_bytes()
        if b'TDC_SIM_DONE' not in data or b'FATAL:' in data:raise RuntimeError('仿真未正常结束')
        analyze(case,3*a.lut_delay)

if __name__=='__main__':main()

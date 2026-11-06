"""独立候选的最小器件MAX-SDF测试；严格注释与时序检查全部保留。"""
from pathlib import Path
import argparse,csv,hashlib,json,re,shutil,subprocess
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02'
SIM=WORK/'sdf';IMPL=WORK/'implementation_F';VIV='F:/Xilinx/Vivado/2022.2/bin'
def run(args,log):
    with log.open('wb') as f:subprocess.run(list(map(str,args)),cwd=SIM,stdout=f,stderr=subprocess.STDOUT,check=True)
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def prepare():
    assert not SIM.exists(),'禁止覆盖SDF试验'
    gate=(IMPL/'TIMING_GATE.txt').read_text();assert 'core_negative_endpoints=0' in gate
    SIM.mkdir();(TASK/'results/sdf').mkdir(exist_ok=True)
    for name in ['post_route_max.sdf','post_route_timing.v']:shutil.copy2(IMPL/name,SIM/name)
    shutil.copy2(TASK/'sim/tb_sdf.sv',SIM/'tb_sdf.sv')
    shutil.copy2(ROOT/'codex_generate/2026-11-05-06-四相TDC-MAX-SDF验证/build/xsim/xsim.ini',SIM/'xsim.ini')
    truth=[];t=5000000
    for case in ['10M_50','20M_50','20M_5','20M_95','10M_20M_switch','adjacent_2ns','phase_boundary']:
        for phase in [1,499,1001,1999]:
            t=((t+1999)//2000)*2000+phase+200000
            for n in range(4):
                period,width={'10M_50':(100000,50000),'20M_50':(50000,25000),'20M_5':(50000,2500),
                    '20M_95':(50000,47500),'adjacent_2ns':(4000,2000),'phase_boundary':(50000,[2499,2500,2501][n%3]),
                    '10M_20M_switch':((100000,50000) if n%2==0 else (50000,25000))}[case]
                truth.append(dict(id=len(truth),case=case,rise_ps=t,fall_ps=t+width,width_ps=width,period_ps=period,phase=phase));t+=period
    with (SIM/'input.txt').open('w') as f:
        for r in truth:f.write(f"{r['id']} {r['rise_ps']} {r['fall_ps']}\n")
    with (TASK/'inputs/SDF_TRUTH.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(truth[0]));w.writeheader();w.writerows(truth)
    shutil.copy2(SIM/'input.txt',TASK/'inputs/SDF_INPUT.txt')
    net=(SIM/'post_route_timing.v').read_text(encoding='utf-8');glbl='' if re.search(r'^module glbl\b',net,re.M) else 'verilog xil_defaultlib "F:/Xilinx/Vivado/2022.2/data/verilog/src/glbl.v"\n'
    (SIM/'compile.prj').write_text('verilog xil_defaultlib "post_route_timing.v"\nsv xil_defaultlib "tb_sdf.sv"\n'+glbl+'nosort\n',encoding='ascii')
    (SIM/'compile.bat').write_text(f'@echo off\ncall "{VIV}/xvlog.bat" --incr --relax -L uvm -prj compile.prj -log xvlog.log\nif errorlevel 1 exit /b 1\ncall "{VIV}/xelab.bat" --O3 --debug off --relax --mt 2 --maxdelay --sdfmax "/tb_sdf/dut=post_route_max.sdf" -L xil_defaultlib -L uvm -L simprims_ver -L secureip --snapshot aux_fall --transport_int_delays --pulse_r 0 --pulse_int_r 0 --pulse_e 0 --pulse_int_e 0 xil_defaultlib.tb_sdf xil_defaultlib.glbl -log elaborate.log\nexit /b %errorlevel%\n',encoding='ascii')
    (SIM/'run_all.tcl').write_text('run all\nquit\n',encoding='ascii')
    (SIM/'run.bat').write_text(f'@echo off\ncall "{VIV}/xsim.bat" aux_fall -tclbatch run_all.tcl -log simulation.log -testplusarg "INPUT={SIM.as_posix()}/input.txt" -testplusarg "OUT={SIM.as_posix()}"\nexit /b %errorlevel%\n',encoding='ascii')
    print('SDF_PREPARED pulses=',len(truth))
def compile_stage():
    run(['cmd.exe','/d','/c','compile.bat'],TASK/'logs/sdf_compile.log')
    log=(SIM/'elaborate.log').read_text(encoding='utf-8',errors='replace')
    warnings=[x for x in log.splitlines() if re.search(r'\b(?:ERROR|WARNING):',x)]
    success='SDF backannotation was successful' in log and 'for root module "/tb_sdf/dut"' in log and not warnings
    sdf=(SIM/'post_route_max.sdf').read_text();constructs={k:len(re.findall(r'\('+k+r'\b',sdf)) for k in ['CELL','IOPATH','INTERCONNECT','SETUPHOLD','WIDTH','PERIOD','RECREM']}
    r=dict(annotation_pass=success,simulator='XSim 2022.2',device='xc7k325tffg900-2',corner='slow/MAX',timing_checks_enabled=True,
       SDF_sha256=sha(SIM/'post_route_max.sdf'),netlist_sha256=sha(SIM/'post_route_timing.v'),constructs_requested=constructs,
       annotation_diagnostics=warnings,interpretation='请求项计数与严格全局成功交叉核对；工具未提供逐条成功读回率')
    shutil.copy2(SIM/'elaborate.log',TASK/'logs/sdf_annotation.log')
    (TASK/'results/sdf/ANNOTATION.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    assert success,r
    print('SDF_ANNOTATION_PASS')
def simulate():
    assert json.loads((TASK/'results/sdf/ANNOTATION.json').read_text(encoding='utf-8'))['annotation_pass']
    assert not (SIM/'timestamps.csv').exists(),'禁止覆盖原仿真'
    run(['cmd.exe','/d','/c','run.bat'],TASK/'logs/sdf_run_console.log')
    tail=(SIM/'simulation.log').read_bytes()[-8192:];assert b'SDF_TEST_COMPLETE' in tail
    for p in SIM.glob('*.csv'):shutil.copy2(p,TASK/'results/sdf'/p.name)
    shutil.copy2(SIM/'simulation.log',TASK/'logs/sdf_simulation.log')
    print('SDF_RUN_COMPLETE; analysis required')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','compile','run']);a=p.parse_args()
    {'prepare':prepare,'compile':compile_stage,'run':simulate}[a.stage]()

"""仅核心门通过后，用官方XSim严格MAX注释，先最小再完整；原日志始终保留。"""
from pathlib import Path
import argparse,gzip,hashlib,json,re,shutil,subprocess,os
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
VIV='F:/Xilinx/Vivado/2022.2/bin'
IMPL=os.environ.get('TDC_SDF_IMPL','implementation_fifo_reuse2')
assert IMPL in ['implementation_H','implementation_H2','implementation_H3','implementation_I','implementation_I_physical','implementation_final','implementation_physical','implementation_H3_physical','implementation_closed','implementation_typepair','implementation_fanout','implementation_fifo_reuse2']
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def core_gate():
    assert 'core_negative_endpoints=0' in (WORK/IMPL/'TIMING_GATE.txt').read_text(),'核心门未通过，禁止SDF'
def run(args,cwd,log,compressed=False):
    with (gzip.open(log,'wb') if compressed else log.open('wb')) as f:
        proc=subprocess.Popen(list(map(str,args)),cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        while chunk:=proc.stdout.read(65536):f.write(chunk)
        rc=proc.wait()
    if rc:raise RuntimeError(f'命令失败rc={rc}，保留日志{log}')
def prepare(variant):
    core_gate();sim=WORK/('sdf_'+variant);assert not sim.exists(),'禁止覆盖SDF运行目录';sim.mkdir()
    src=WORK/(IMPL if variant=='corrected' else 'baseline_export')
    for name in ['post_route_max.sdf','post_route_timing.v']:shutil.copy2(src/name,sim/name)
    shutil.copy2(TASK/'sim/tb_sdf.sv',sim/'tb_sdf.sv')
    shutil.copy2(ROOT/'codex_generate/2026-11-05-06-四相TDC-MAX-SDF验证/build/xsim/xsim.ini',sim/'xsim.ini')
    net=(sim/'post_route_timing.v').read_text(encoding='utf-8');assert '$sdf_annotate' not in net
    glbl='' if re.search(r'^module glbl\b',net,re.M) else 'verilog xil_defaultlib "F:/Xilinx/Vivado/2022.2/data/verilog/src/glbl.v"\n'
    extra=int(variant=='corrected' and 'coarse_counter_d1' in net)
    define=' -d "FRONTEND_PIPE1="' if extra else ''
    (sim/'compile.prj').write_text('verilog xil_defaultlib "post_route_timing.v"\nsv xil_defaultlib'+define+' "tb_sdf.sv"\n'+glbl+'nosort\n',encoding='ascii')
    dcp=src/'corrected_routed.dcp' if variant=='corrected' else WORK/'production_AD23.dcp'
    (sim/'SOURCE.json').write_text(json.dumps(dict(input_extra_cycles=extra,DCP_sha256=sha(dcp),SDF_sha256=sha(sim/'post_route_max.sdf'),netlist_sha256=sha(sim/'post_route_timing.v')),indent=2),encoding='utf-8')
    (sim/'compile.bat').write_text(f'@echo off\ncall "{VIV}/xvlog.bat" --incr --relax -L uvm -prj compile.prj -log xvlog.log\nif errorlevel 1 exit /b 1\ncall "{VIV}/xelab.bat" --O3 --debug off --relax --mt 2 --maxdelay --sdfmax "/tb_sdf/dut=post_route_max.sdf" -L xil_defaultlib -L uvm -L simprims_ver -L secureip --snapshot aux_match --transport_int_delays --pulse_r 0 --pulse_int_r 0 --pulse_e 0 --pulse_int_e 0 xil_defaultlib.tb_sdf xil_defaultlib.glbl -log elaborate.log\nexit /b %errorlevel%\n',encoding='ascii')
    (sim/'run_all.tcl').write_text('run all\nquit\n',encoding='ascii')
    print('SDF_PREPARED',variant,flush=True)
def compile_stage(variant):
    core_gate();sim=WORK/('sdf_'+variant);out=TASK/'results/sdf'/variant;out.mkdir(parents=True,exist_ok=True)
    run(['cmd.exe','/d','/c','compile.bat'],sim,TASK/'logs'/f'sdf_{variant}_compile.log')
    log=(sim/'elaborate.log').read_text(encoding='utf-8',errors='replace')
    warnings=[x for x in log.splitlines() if re.search(r'\b(?:ERROR|WARNING):',x)]
    success='SDF backannotation was successful' in log and 'for root module "/tb_sdf/dut"' in log and not warnings
    sdf=(sim/'post_route_max.sdf').read_text();constructs={k:len(re.findall(r'\('+k+r'\b',sdf)) for k in ['CELL','IOPATH','INTERCONNECT','SETUPHOLD','WIDTH','PERIOD','RECREM']}
    source=json.loads((sim/'SOURCE.json').read_text(encoding='utf-8'))
    result=dict(annotation_pass=success,simulator='Vivado XSim 2022.2',corner='slow/MAX',device='xc7k325tffg900-2',timing_checks_enabled=True,input_extra_cycles=source['input_extra_cycles'],DCP_sha256=source['DCP_sha256'],
        native_global_annotation_success=success,zero_unmatched_diagnostics=not warnings,constructs_requested=constructs,
        SDF_sha256=sha(sim/'post_route_max.sdf'),netlist_sha256=sha(sim/'post_route_timing.v'),diagnostics=warnings,
        note='工具提供严格全局成功；请求项计数不是逐条成功率读回。没有关闭specify、timing check或互连延迟。')
    (out/'ANNOTATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');shutil.copy2(sim/'elaborate.log',TASK/'logs'/f'sdf_{variant}_annotation.log')
    assert success,result
    print('SDF_ANNOTATION_PASS',variant,flush=True)
def simulate(variant,dataset):
    core_gate();sim=WORK/('sdf_'+variant);out=TASK/'results/sdf'/variant
    assert json.loads((out/'ANNOTATION.json').read_text(encoding='utf-8'))['annotation_pass']
    if variant=='corrected' and dataset=='full':
        # 先完成最小测试并保留结果；即使边界压力失败，也需用原完整激励明确实际验收范围。
        assert (out/'minimal/SUMMARY.json').exists(),'先分析最小测试，不跳过失败证据'
    case=sim/dataset;assert not case.exists(),'禁止覆盖原始SDF输出';case.mkdir()
    shutil.copy2(TASK/'inputs'/(dataset+'.txt'),case/'stimulus.txt')
    shutil.copy2(TASK/'inputs'/(dataset+'_truth.csv'),case/'truth.csv')
    bat=case/'run.bat';log=case/'simulation.log'
    bat.write_text(f'@echo off\ncall "{VIV}/xsim.bat" aux_match -tclbatch run_all.tcl -log "{log.as_posix()}" -testplusarg "INPUT={case.as_posix()}/stimulus.txt" -testplusarg "OUT={case.as_posix()}"\nexit /b %errorlevel%\n',encoding='ascii')
    run(['cmd.exe','/d','/c',bat],sim,case/'console.log.gz',compressed=True)
    with log.open('rb') as f:f.seek(max(0,log.stat().st_size-8192));tail=f.read()
    assert b'SDF_TEST_COMPLETE' in tail,'仿真未正常结束'
    dest=out/dataset;dest.mkdir(exist_ok=True)
    for p in case.glob('*.csv'):shutil.copy2(p,dest/p.name)
    with log.open('rb') as src,gzip.open(dest/'simulation.log.gz','wb') as dst:shutil.copyfileobj(src,dst)
    (dest/'RUN_MANIFEST.json').write_text(json.dumps(dict(completed=True,variant=variant,dataset=dataset,
        timing_checks_enabled=True,stimulus_sha256=sha(case/'stimulus.txt'),truth_sha256=sha(case/'truth.csv'),
        native_simulation_log=str(log),native_log_sha256=sha(log),compressed_log_sha256=sha(dest/'simulation.log.gz')),ensure_ascii=False,indent=2),encoding='utf-8')
    print('SDF_SIMULATION_COMPLETE',variant,dataset,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','compile','run']);p.add_argument('--variant',choices=['corrected','baseline'],default='corrected');p.add_argument('--dataset',choices=['minimal','full'],default='minimal');a=p.parse_args()
    {'prepare':lambda:prepare(a.variant),'compile':lambda:compile_stage(a.variant),'run':lambda:simulate(a.variant,a.dataset)}[a.stage]()

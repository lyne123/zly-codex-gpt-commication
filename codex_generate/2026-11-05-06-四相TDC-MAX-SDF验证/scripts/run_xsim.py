"""ModelSim注释不充分时，使用Vivado配套真实时序库；仍冻结同一DCP/网表/SDF。"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess
ROOT=Path('Z:/');VIV='F:/Xilinx/Vivado/2022.2/bin'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(args,cwd,log):
    with log.open('wb') as f:subprocess.run([str(x) for x in args],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,check=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','compile','annotate','full']);a=p.parse_args();work=ROOT/'build/xsim'
    if a.action=='prepare':
        work.mkdir(exist_ok=True)
        for src,dst in [(ROOT/'netlist/post_route_timing.v',work/'post_route_timing.v'),(ROOT/'netlist/post_route_max.sdf',work/'post_route_max.sdf'),(ROOT/'sim/tb_tdc_sdf.sv',work/'input_tb.sv'),(ROOT/'sim/gate_observer.svh',work/'gate_observer.svh'),(ROOT/'sim/fifo_reset_observer.svh',work/'fifo_reset_observer.svh'),(Path('U:/inputs/xsim.ini'),work/'xsim.ini')]:
            shutil.copyfile(src,dst);assert sha(src)==sha(dst)
        (work/'compile.prj').write_text('verilog xil_defaultlib "post_route_timing.v"\nsv xil_defaultlib -d "GATE_NETLIST=" -d "OPTIMIZED_GATE_NETLIST=" "input_tb.sv"\nnosort\n',encoding='ascii')
        (work/'compile.bat').write_text(f'@echo off\ncall "{VIV}/xvlog.bat" --incr --relax -L uvm -prj compile.prj -log xvlog.log\nif errorlevel 1 exit /b 1\ncall "{VIV}/xelab.bat" --O3 --debug off --relax --mt 2 --maxdelay --sdfmax "/tb_tdc/dut=post_route_max.sdf" -L xil_defaultlib -L uvm -L simprims_ver -L secureip --snapshot measurement --transport_int_delays --pulse_r 0 --pulse_int_r 0 --pulse_e 0 --pulse_int_e 0 xil_defaultlib.tb_tdc xil_defaultlib.glbl -log elaborate.log\nexit /b %errorlevel%\n',encoding='ascii')
        (work/'run_zero.tcl').write_text('run 0 ns\nquit\n',encoding='ascii');(work/'run_all.tcl').write_text('run all\nquit\n',encoding='ascii')
        print('XSIM_PREPARED; same netlist/SDF hashes; external annotation only');return
    if a.action=='compile':
        run(['cmd.exe','/d','/c','compile.bat'],work,ROOT/'logs/compile_xsim.log')
        shutil.copyfile(work/'elaborate.log',ROOT/'logs/sdf_annotation_xsim.log')
        print('XSIM_COMPILE_AND_ANNOTATION_COMPLETE');return
    if a.action=='full':
        coverage=json.loads((ROOT/'results/SDF_COVERAGE.json').read_text(encoding='utf-8'));assert coverage['annotation_pass'] and coverage['accepted_simulator']=='XSim 2022.2'
        case=ROOT/'results/compensated/gate_full'
    else:case=ROOT/'results/xsim_annotation_probe'
    if case.exists():raise RuntimeError('禁止覆盖已有结果：'+str(case))
    case.mkdir(parents=True)
    for src,dst in [('full.txt','stimulus.txt'),('full_truth.csv','truth.csv')]:shutil.copyfile(ROOT/'inputs'/src,case/dst)
    log=ROOT/'logs'/('simulation.log' if a.action=='full' else 'xsim_zero.log')
    script=case/'run.bat';tcl='run_all.tcl' if a.action=='full' else 'run_zero.tcl'
    script.write_text(f'@echo off\ncall "{VIV}/xsim.bat" measurement -tclbatch {tcl} -log "{log.as_posix()}" -testplusarg "STIMULUS={case.as_posix()}/stimulus.txt" -testplusarg "OUTPUT_DIR={case.as_posix()}" -testplusarg "TIME_SHIFT=0"\nexit /b %errorlevel%\n',encoding='ascii')
    run(['cmd.exe','/d','/c',str(script)],work,case/'console.log')
    if a.action=='full':
        with log.open('rb') as f:f.seek(max(0,log.stat().st_size-8192));tail=f.read()
        assert b'TDC_SIM_DONE' in tail,'完整SDF仿真未正常结束'
        (case/'run_manifest.txt').write_text('level=gate\nvariant=compensated\ndataset=full\ncorner=slow/MAX\nsimulator=XSim 2022.2\ntiming_checks=enabled\nstimulus_count=3512\n',encoding='ascii')
    print('XSIM_STAGE_FINISHED',a.action,flush=True)
if __name__=='__main__':main()

"""同一冻结激励用于四组对照；编译快照及SDF来源逐次记录。"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess

ROOT=Path('U:/')
OLD=Path('T:/')
VIVADO=Path('F:/Xilinx/Vivado/2022.2/bin')

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def execute(args,cwd,log):
    with log.open('wb') as f:
        result=subprocess.run(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(f'进程失败 {result.returncode}，详见 {log}')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=['original','optimized'])
    p.add_argument('variant',choices=['baseline','compensated'])
    p.add_argument('level',choices=['rtl','gate'])
    p.add_argument('dataset',choices=['calibration','validation','fifo_probe'])
    a=p.parse_args()
    parent=ROOT/'results'/a.phase/a.variant
    case=parent/f'{a.level}_{a.dataset}'
    if (case/'widths.csv').exists():raise RuntimeError('禁止覆盖测量证据')
    case.mkdir(parents=True,exist_ok=True)
    work=ROOT/'build'/f'{a.level}_{a.phase}_{a.variant}'
    work.mkdir(parents=True,exist_ok=True)
    if a.level=='gate' and a.phase=='original' and not (parent/'design.dcp').exists():
        for src,dest in [('design.dcp','design.dcp'),('annotated_design.v','design.v'),('annotated_design.sdf','design.sdf')]:
            shutil.copyfile(OLD/'results'/a.variant/src,parent/dest)
    if not (work/'prepared.ok').exists():
        shutil.copyfile(ROOT/'sim/tb_tdc.sv',work/'input_tb.sv')
        if a.level=='rtl':
            files=sorted((ROOT/'original'/a.variant/'rtl' if a.phase=='original' else ROOT/'rtl').glob('*.v'))
            args=['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_tdc','-I',str(work),'-o',str(work/'simulation.vvp')]
            if a.variant=='compensated':
                paramfile=ROOT/'inputs/old_tdc_skew_calibration.csv' if a.phase=='original' else ROOT/'results/tdc_skew_calibration.csv'
                rows=list(csv.DictReader(paramfile.open(encoding='utf-8-sig')))
                params=['.ENABLE_SKEW_COMP(1)']+[f".{r['polarity'].upper()}_OFFSET_{r['tdl_phase']}_PS(18'sd{r['offset_ps']})" for r in rows]
                (work/'compensation_parameters.vh').write_text('`define COMPENSATION_PARAMETERS #('+','.join(params)+')\n',encoding='ascii')
                args+=['-DCOMPENSATED_RTL']
            args += [str(work/'input_tb.sv'),str(ROOT/'sim/functional_models.v')]+[str(f) for f in files]
            execute(args,work,work/'compile.log')
        else:
            netlist=parent/'design.v'
            text=netlist.read_text(encoding='utf-8')
            matches=re.findall(r'\$sdf_annotate\("([^\"]+)"',text)
            if len(matches)!=1:raise RuntimeError('必须有且仅有一处静态SDF注释')
            shutil.copyfile(netlist,work/'design.v')
            shutil.copyfile(parent/'design.sdf',work/matches[0])
            ini=ROOT/'inputs/xsim.ini'
            shutil.copyfile(ini,work/'xsim.ini')
            # 仅读取实际网表中粗计数总线名称，定义观察点适配宏，不编辑网表。
            observer_macro=' -d "OPTIMIZED_GATE_NETLIST="' if re.search(r'wire\s+\[9:0\]\s*coarse_counter\s*;',text) else ''
            (work/'compile.prj').write_text('verilog xil_defaultlib -d "GATE_NETLIST=" "design.v"\nsv xil_defaultlib -d "GATE_NETLIST="'+observer_macro+' "input_tb.sv"\nnosort\n',encoding='ascii')
            commands=[f'call "{VIVADO}/xvlog.bat" --incr --relax -L uvm -prj compile.prj -log xvlog.log',
                # 官方O3优化及关闭波形调试可降低开销；全部MAX SDF/timing checks仍启用。
                f'call "{VIVADO}/xelab.bat" --incr --O3 --debug off --relax --mt 2 --maxdelay -d "GATE_NETLIST=" -L xil_defaultlib -L uvm -L simprims_ver -L secureip --snapshot measurement -transport_int_delays -pulse_r 0 -pulse_int_r 0 -pulse_e 0 -pulse_int_e 0 xil_defaultlib.tb_tdc xil_defaultlib.glbl -log elaborate.log']
            (work/'compile.bat').write_text('@echo off\n'+('\nif errorlevel 1 exit /b 1\n'.join(commands))+'\nexit /b %errorlevel%\n',encoding='ascii')
            execute(['cmd.exe','/d','/c','compile.bat'],work,work/'compile_console.log')
            log=(work/'elaborate.log').read_text(errors='replace')
            if 'ERROR:' in log:raise RuntimeError('SDF展开错误，禁止运行')
        (work/'prepared.ok').write_text('compiled\n',encoding='ascii')
    for src,dest in [(work/'input_tb.sv','input_tb.sv'),(ROOT/'sim/stimuli'/f'{a.dataset}.txt','stimulus.txt'),(ROOT/'sim/stimuli'/f'{a.dataset}_truth.csv','truth.csv')]:shutil.copyfile(src,case/dest)
    if a.level=='rtl':
        args=['F:/iverilog/bin/vvp.exe',str(work/'simulation.vvp'),f'+STIMULUS={case.as_posix()}/stimulus.txt',f'+OUTPUT_DIR={case.as_posix()}']
        execute(args,work,case/'simulation.log')
    else:
        shutil.copyfile(work/'elaborate.log',case/'elaboration.log')
        # 每个数据集独立运行目录，避免并行复用快照时互相覆盖xsim脚本或journal。
        run_work=ROOT/'build'/f'gate_run_{a.phase}_{a.variant}_{a.dataset}'
        if not run_work.exists():
            run_work.mkdir()
            shutil.copytree(work/'xsim.dir',run_work/'xsim.dir')
            shutil.copyfile(work/'xsim.ini',run_work/'xsim.ini')
            shutil.copyfile(work/'design.v',run_work/'design.v')
            text=(work/'design.v').read_text(encoding='utf-8')
            sdf_name=re.findall(r'\$sdf_annotate\("([^\"]+)"',text)[0]
            shutil.copyfile(work/sdf_name,run_work/sdf_name)
        (run_work/'run_all.tcl').write_text('run all\nquit\n',encoding='ascii')
        # XSim会经过Tcl解析，参数路径必须使用正斜杠，避免反斜杠被当作转义。
        command=f'@echo off\ncall "{VIVADO.as_posix()}/xsim.bat" measurement -tclbatch run_all.tcl -log "{case.as_posix()}/simulation.log" -testplusarg "STIMULUS={case.as_posix()}/stimulus.txt" -testplusarg "OUTPUT_DIR={case.as_posix()}"\nexit /b %errorlevel%\n'
        (case/'run_xsim.bat').write_text(command,encoding='ascii')
        execute(['cmd.exe','/d','/c',str(case/'run_xsim.bat')],run_work,case/'console.log')
    with (case/'simulation.log').open('rb') as f:
        f.seek(max(0,(case/'simulation.log').stat().st_size-8192));tail=f.read()
    if b'TDC_SIM_DONE' not in tail:raise RuntimeError('没有正常结束标记')
    sources=[case/'input_tb.sv',case/'stimulus.txt',case/'truth.csv']
    if a.level=='gate':sources+=[parent/'design.v',parent/'design.sdf',parent/'design.dcp']
    else:
        sources+=sorted((ROOT/'original'/a.variant/'rtl' if a.phase=='original' else ROOT/'rtl').glob('*.v'))
        if a.variant=='compensated':sources.append(work/'compensation_parameters.vh')
    metadata={str(f):{'sha256':sha(f),'bytes':f.stat().st_size} for f in sources}
    (case/'input_sha256.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    outputs=['raw.csv','candidate.csv','timestamps.csv','widths.csv','errors.csv','fifo.csv','sampled_taps.csv','clock_epoch.csv','error_fifo.csv','anomaly_pipeline_trace.csv']
    (case/'raw_output_sha256.json').write_text(json.dumps({n:dict(bytes=(case/n).stat().st_size,sha256=sha(case/n)) for n in outputs},indent=2),encoding='utf-8')
    (case/'run_manifest.txt').write_text(f'level={a.level}\nphase={a.phase}\nvariant={a.variant}\ndataset={a.dataset}\ntiming_checks=enabled_for_gate\n',encoding='ascii')
    print(f'SIMULATION_DONE {case}',flush=True)

if __name__=='__main__':main()

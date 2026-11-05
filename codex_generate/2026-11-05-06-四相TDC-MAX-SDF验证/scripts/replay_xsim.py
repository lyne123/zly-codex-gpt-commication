"""独立复现已归档的真实MAX-SDF仿真；不依赖原机器盘符，不覆盖验收数据。"""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vivado', required=True, type=Path, help='Vivado 2022.2安装根目录')
    parser.add_argument('--output-name', default='replay_xsim', help='build内尚不存在的目录名')
    args = parser.parse_args()
    root = Path(__file__).absolute().parent.parent
    assert Path(args.output_name).name == args.output_name and args.output_name not in ('.', '..')
    work = root / 'build' / args.output_name
    assert not work.exists(), '禁止覆盖已有复现目录'
    assert str(work).isascii(), '请先subst短ASCII盘符，再从该盘符执行本脚本'
    version = subprocess.check_output([str(args.vivado / 'bin/xelab.bat'), '--version'], text=True)
    assert '2022.2' in version, version
    exported = json.loads((root / 'inputs/EXPORTED_FILES.json').read_text(encoding='utf-8'))
    assert sha(root / 'netlist/post_route_timing.v') == exported['netlist_sha256']
    assert sha(root / 'netlist/post_route_max.sdf') == exported['SDF_sha256']
    for line in (root / 'inputs/stimulus_sha256.txt').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert sha(root / 'inputs' / name) == digest
    work.mkdir(parents=True)
    for source, target in [('netlist/post_route_timing.v', 'post_route_timing.v'),
                           ('netlist/post_route_max.sdf', 'post_route_max.sdf'),
                           ('sim/tb_tdc_sdf.sv', 'input_tb.sv'),
                           ('sim/gate_observer.svh', 'gate_observer.svh'),
                           ('sim/fifo_reset_observer.svh', 'fifo_reset_observer.svh'),
                           ('inputs/full.txt', 'stimulus.txt'),
                           ('inputs/full_truth.csv', 'truth.csv')]:
        shutil.copyfile(root / source, work / target)
    shutil.copyfile(args.vivado / 'data/xsim/xsim.ini', work / 'xsim.ini')
    (work / 'compile.prj').write_text('verilog xil_defaultlib "post_route_timing.v"\nsv xil_defaultlib -d "GATE_NETLIST=" -d "OPTIMIZED_GATE_NETLIST=" "input_tb.sv"\nnosort\n', encoding='ascii')
    (work / 'run_all.tcl').write_text('run all\nquit\n', encoding='ascii')
    # 与正式验收相同的编译/时序选项，只将输出改到新的build子目录。
    bindir = (args.vivado / 'bin').as_posix()
    batch = f'''@echo off
call "{bindir}/xvlog.bat" --incr --relax -L uvm -prj compile.prj -log xvlog.log
if errorlevel 1 exit /b 1
call "{bindir}/xelab.bat" --O3 --debug off --relax --mt 2 --maxdelay --sdfmax "/tb_tdc/dut=post_route_max.sdf" -L xil_defaultlib -L uvm -L simprims_ver -L secureip --snapshot measurement --transport_int_delays --pulse_r 0 --pulse_int_r 0 --pulse_e 0 --pulse_int_e 0 xil_defaultlib.tb_tdc xil_defaultlib.glbl -log elaborate.log
if errorlevel 1 exit /b 1
call "{bindir}/xsim.bat" measurement -tclbatch run_all.tcl -log simulation.log -testplusarg "STIMULUS={work.as_posix()}/stimulus.txt" -testplusarg "OUTPUT_DIR={work.as_posix()}" -testplusarg "TIME_SHIFT=0"
exit /b %errorlevel%
'''
    (work / 'replay.bat').write_text(batch, encoding='ascii')
    with (work / 'console.log').open('wb') as log:
        subprocess.run(['cmd.exe', '/d', '/c', 'replay.bat'], cwd=work, stdout=log, stderr=subprocess.STDOUT, check=True)
    with (work / 'simulation.log').open('rb') as log:
        log.seek(max(0, (work / 'simulation.log').stat().st_size - 8192))
        assert b'TDC_SIM_DONE' in log.read()
    print('真实MAX-SDF复现已完成，原验收结果未覆盖：', work)


if __name__ == '__main__':
    main()

"""最小复现入口：冻结网表的一个 Baseline 局部 MAX-SDF 实验。"""
from pathlib import Path
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def run(command,cwd,log=None):
    if log:
        with log.open('wb') as f:
            subprocess.run(command,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,check=True)
    else: subprocess.run(command,cwd=cwd,check=True)

def main():
    # Vivado 的 Tcl 和 SDF 运行目录使用短 ASCII 路径，避免中文路径兼容问题。
    if not Path('V:/scripts/prepare.py').exists():
        raise SystemExit('先将本任务目录映射为 V:，见 FRONTEND_ROOT_CAUSE.md。')
    if any((ROOT/name).exists() for name in ['results/short_baseline/simulation.log','results/short_baseline/raw.csv','EVENT_DIAGNOSIS.csv']):
        raise SystemExit('结果已存在；为保护证据，请在单独的新副本复现。')
    run([sys.executable,str(ROOT/'scripts/prepare.py')],ROOT)
    work=Path('V:/build/short_baseline')
    run(['cmd.exe','/d','/c','compile.bat'],work,ROOT/'logs/compile_console.log')
    run(['cmd.exe','/d','/c','run.bat'],work,ROOT/'logs/run_console.log')
    run([sys.executable,str(ROOT/'scripts/check_equivalence.py')],ROOT)
    run([sys.executable,str(ROOT/'scripts/audit_run.py')],ROOT)
    run([sys.executable,str(ROOT/'scripts/build_diagnosis.py')],ROOT)

if __name__=='__main__':main()

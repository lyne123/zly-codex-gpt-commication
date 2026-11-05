"""先编译及0时刻注释核验，再单次运行全部3512脉冲；禁止覆盖结果。"""
from pathlib import Path
import argparse,json,shutil,subprocess
ROOT=Path('Z:/');MSIM=Path('F:/Program Files/modeltech64_2020.4/win64')
def run(args,cwd,log):
    with log.open('wb') as f:return subprocess.run([str(x) for x in args],cwd=cwd,stdout=f,stderr=subprocess.STDOUT).returncode
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['compile','annotate','full']);p.add_argument('--tag',default='');p.add_argument('--novopt',action='store_true');p.add_argument('--legacy-compat',action='store_true');p.add_argument('--conditional-ntc',action='store_true');a=p.parse_args();work=ROOT/'build/modelsim'
    if a.action=='compile':
        args=[MSIM/'vlog.exe','-modelsimini',work/'modelsim.ini','-work','work','-sv','+define+XIL_TIMING','+define+GATE_NETLIST','+define+OPTIMIZED_GATE_NETLIST','+incdir+Z:/sim','-f',work/'design_files.f']
        rc=run(args,work,ROOT/'logs/compile.log');print('COMPILE_EXIT',rc);raise SystemExit(rc)
    if a.action=='full':
        coverage=json.loads((ROOT/'results/SDF_COVERAGE.json').read_text(encoding='utf-8'));assert coverage['annotation_pass'] and coverage['accepted_simulator']=='ModelSim SE-64 2020.4','本仿真器的注释覆盖未通过，不运行完整激励'
        case=ROOT/'results/compensated/gate_full'
    else:case=ROOT/('results/annotation_probe'+a.tag)
    if case.exists():raise RuntimeError('禁止覆盖已运行结果：'+str(case))
    case.mkdir(parents=True)
    for src,dst in [('full.txt','stimulus.txt'),('full_truth.csv','truth.csv')]:shutil.copyfile(ROOT/'inputs'/src,case/dst)
    args=json.loads((ROOT/'inputs/SIMULATION_COMMAND.json').read_text())
    if a.novopt:
        args.remove('-voptargs=+acc');args+=['-novopt','+ntc_warn']
        # 12110仅为-novopt性能/弃用提示，不是SDF或时序检查消息；原提示日志保留。
        if a.legacy_compat:args+=['-suppress','12110']
    if a.conditional_ntc:
        # 2020.4原版手册981页：level3按条件求解负检查，保留全部检查而非忽略负限值。
        args+=['-glsnegtchk','level3','+ntc_warn','+maxdelays']
        args=[x for x in args if x not in ['+pulse_int_r/0','+pulse_int_e/0','+pulse_r/0','+pulse_e/0']]
    args+=['-sdfreport='+str(ROOT/'logs'/('sdf_annotation'+a.tag+'_unannotated.log' if a.action=='annotate' else 'sdf_full_unannotated.log'))]
    args+=['+STIMULUS='+str(case/'stimulus.txt'),'+OUTPUT_DIR='+str(case),'+TIME_SHIFT=0','-do','run 0; quit -f' if a.action=='annotate' else 'do Z:/sim/simulation.do']
    (case/'RUN_COMMAND.json').write_text(json.dumps(args,indent=2),encoding='utf-8')
    logfile=ROOT/'logs'/('sdf_annotation'+a.tag+'.log' if a.action=='annotate' else 'simulation.log')
    rc=run(args,work,logfile)
    if a.action=='full':
        tail=logfile.read_bytes()[-8192:];assert rc==0 and b'TDC_SIM_DONE' in tail,'完整SDF仿真未正常结束'
        (case/'run_manifest.txt').write_text('level=gate\nvariant=compensated\ndataset=full\ncorner=slow/MAX\nsimulator=ModelSim SE-64 2020.4\ntiming_checks=enabled\nstimulus_count=3512\n',encoding='ascii')
    print('MODELSIM_STAGE_FINISHED',a.action,'exit',rc,flush=True);raise SystemExit(rc)
if __name__=='__main__':main()

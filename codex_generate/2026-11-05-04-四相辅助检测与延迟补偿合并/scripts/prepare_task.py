"""冻结四个版本及原参数；不改正式RTL或历史实验。"""
from pathlib import Path
import csv,difflib,hashlib,json,shutil,subprocess

ROOT=Path(__file__).resolve().parents[1]
PREV=ROOT.parent/'2026-11-05-03-四相TDC辅助边沿检测优化'
OLD=ROOT.parent/'2026-11-05-01-四相TDC时序优化与连续测量验证'
REPO=PREV/'github'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    versions={'baseline_original':OLD/'original/rtl','baseline_aux4':PREV/'rtl','compensated_previous':OLD/'rtl'}
    manifest={}
    for label,source in versions.items():
        dest=ROOT/'original'/label;dest.mkdir(exist_ok=True)
        for p in source.glob('*.v'):shutil.copyfile(p,dest/p.name)
        manifest[label]={p.name:sha(p) for p in dest.glob('*.v')}
    for p in (PREV/'rtl').glob('*.v'):shutil.copyfile(p,ROOT/'rtl'/p.name)
    for name in ['tdc_meas_top.v','tdc_time_locate.v','tdc_time_candicate.v','tdc_time_merge.v']:
        assert sha(ROOT/'rtl'/name)==sha(OLD/'rtl'/name),name
    for name in ['frozen_compensation.csv','frozen_baseline_association.json','combine.xdc']:
        shutil.copyfile(PREV/'inputs'/name,ROOT/'inputs'/name)
    shutil.copytree(PREV/'inputs/ip',ROOT/'inputs/ip',dirs_exist_ok=True)
    shutil.copyfile(OLD/'results/optimized/compensated/parameters_used.tcl',ROOT/'inputs/compensation_params.tcl')
    assert sha(ROOT/'inputs/frozen_compensation.csv')==sha(OLD/'results/tdc_skew_calibration.csv')
    rows=list(csv.DictReader((ROOT/'inputs/frozen_compensation.csv').open(encoding='utf-8-sig')))
    assert len(rows)==8
    overrides=['.ENABLE_SKEW_COMP(1)']
    for r in rows:
        value=int(r['offset_ps']);literal=("-18'sd"+str(-value)) if value<0 else ("18'sd"+str(value))
        overrides.append(f".{r['polarity'].upper()}_OFFSET_{r['tdl_phase']}_PS({literal})")
    (ROOT/'sim/compensation_parameters.vh').write_text('`define COMPENSATION_PARAMETERS #('+','.join(overrides)+')\n',encoding='ascii')
    for name in ['tb_quick.sv','functional_models.v','aux_monitor.svh']:
        shutil.copyfile(PREV/'sim'/name,ROOT/'sim'/name)
    shutil.copytree(PREV/'sim/stimuli',ROOT/'sim/stimuli',dirs_exist_ok=True)
    for name in ['restore_bram_mode.tcl','prepare_ila_cluster.tcl','register_ip.tcl']:
        shutil.copyfile(PREV/'scripts'/name,ROOT/'scripts'/name)
    # 保留源commit内的原始文件路径及对象SHA，避免把本地副本误认成新算法。
    provenance={}
    for commit,folder in [('d30dfeb9779f7d3c4859fbfb300bebd2d9481a7b',OLD.name),('6b341d88497541f23eaefee1cfad4e4925c7f2aa',PREV.name)]:
        paths=['rtl/'+p.name for p in (OLD/'rtl').glob('*.v')]
        if folder==OLD.name:paths+=['results/optimized/compensated/parameters_used.tcl','results/tdc_skew_calibration.csv']
        for path in paths:
            data=subprocess.check_output(['git','-C',str(REPO),'show',commit+':codex_generate/'+folder+'/'+path])
            local=(OLD if folder==OLD.name else PREV)/path
            assert data.replace(b'\r\n',b'\n')==local.read_bytes().replace(b'\r\n',b'\n'),path
            provenance[commit+':'+path]={'local_path':str(local),'sha256':sha(local),'git_blob':subprocess.check_output(['git','-C',str(REPO),'rev-parse',commit+':codex_generate/'+folder+'/'+path],text=True).strip()}
    manifest['new_compensated']={p.name:sha(p) for p in (ROOT/'rtl').glob('*.v')}
    (ROOT/'inputs/SOURCE_PROVENANCE.json').write_text(json.dumps({'versions':manifest,'git_evidence':provenance,'parameters_recalculated':False},ensure_ascii=False,indent=2),encoding='utf-8')
    diffs=[]
    for p in (ROOT/'rtl').glob('*.v'):
        before=(ROOT/'original/compensated_previous'/p.name).read_text(encoding='utf-8');after=p.read_text(encoding='utf-8')
        diffs+=difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='previous_compensated/'+p.name,tofile='new_compensated/'+p.name)
    (ROOT/'RTL.diff').write_text(''.join(diffs),encoding='utf-8')
    (ROOT/'MERGE_PLAN.md').write_text('''# 合并方案及来源

原Compensated：d30dfeb9779f7d3c4859fbfb300bebd2d9481a7b，上一轮任务results/optimized/compensated。
已验证四相辅助Baseline：6b341d88497541f23eaefee1cfad4e4925c7f2aa。

正式工程及历史版本均不覆盖。新独立实现的5个RTL与四相辅助Baseline逐字节一致。
相对于原Compensated，仅tdc_fine_layer.v发生辅助检测变更；top/locate/candidate/merge逐字节一致。
合并通过综合generic及RTL测试平台参数启用原有补偿，不重新实现补偿代码。

补偿在候选选择之后、Time Locate第2/3级计算。原有18位有符号参数、19位中细运算、21位时间戳、扩展符号运算及模2048000ps回卷保持不变；单位ps，10ps/tap，没有新增舍入。
sel_index 0/1/2/3对应90°/180°/270°/下一周期0°，不能直接当物理TDL序号。
8参数由旧独立SDF校准冻结，包含公共流水线；rise/fall分别选择，虽然本次冻结数值相等。
新RTL的辅助流水线、采样顺序、去重/归属和confirm_edge均不修改。

修改/新增文件清单：本任务rtl副本(相对于原Compensated仅fine_layer变化)、inputs/compensation_params.tcl、sim/compensation_parameters.vh、验证/构建/报告脚本；codex_generate/README.md新增索引。
先RTL全3512及补偿边界检查，再综合实现和完整MAX-SDF；任一失败停止后续依赖步骤，BIT另设验收门槛。
''',encoding='utf-8')
    index=ROOT.parent/'README.md';data=index.read_bytes()
    if ROOT.name.encode() not in data:
        eol=b'\r\n' if b'\r\n' in data else b'\n';row=f'| 2026-11-05-04 | [四相辅助检测与延迟补偿合并]({ROOT.name}/RESULTS.md) |'.encode()
        pos=data.index(b'\n',data.index(b'| 2026-11-05-03 |'))+1
        index.write_bytes(data[:pos]+row+eol+data[pos:])
    print('SOURCE_FOUND_AND_FROZEN',len(provenance),'Git source objects; original parameters retained')

if __name__=='__main__':main()

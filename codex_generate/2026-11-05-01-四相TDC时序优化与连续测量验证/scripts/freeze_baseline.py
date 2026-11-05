"""选定独立试验为新Baseline，先保存旧目录及原RTL仿真证据。"""
from pathlib import Path
import hashlib
import json
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    chosen=(ROOT/'results/trials/baseline_ila_cluster_relaxed').resolve()
    current=(ROOT/'results/optimized/baseline').resolve()
    saved=(ROOT/'build/preserved_baseline_initial_canonical').resolve()
    # Windows目录移动前验证所有绝对目标均位于本任务根目录，且不覆盖旧副本。
    for p in [chosen,current,saved]:assert p.is_relative_to(ROOT.resolve()),str(p)
    assert not saved.exists() and (chosen/'Baseline_Optimized.bit').exists()
    assert not re.search(r'\|\s*Error\s*\|',(chosen/'drc.rpt').read_text(errors='replace'))
    assert 'UTLZ-3' not in (chosen/'drc.rpt').read_text(errors='replace'),'禁止使用容量不足的局部区域'
    files=['design.dcp','design.v','design.sdf','Baseline_Optimized.bit']
    assert all(sha(current/n)==sha(ROOT/'results/trials/baseline_initial'/n) for n in files)
    print(json.dumps(dict(source=str(current),preserved_as=str(saved),selected=str(chosen)),ensure_ascii=False),flush=True)
    current.rename(saved)
    shutil.copytree(chosen,current)
    for name in ['rtl_calibration','rtl_validation']:shutil.copytree(saved/name,current/name)
    provenance=dict(selected_trial='results/trials/baseline_ila_cluster_relaxed',copied_byte_identically=True,
        chain=['baseline_initial','baseline_power_replicated','baseline_ila_cluster','baseline_ila_cluster_relaxed'],
        actual_recipe='unroute frozen initial DCP; preplace BRAM power optimization; local ILA counter cluster with capacity 80 Slices; ExtraPostPlacementOpt; AggressiveExplore physical optimization; Explore routing',
        metadata_note='baseline_power_replicated build_metadata中的source=Explore_opt_checkpoint为旧描述；实际输入为冻结baseline_initial/design.dcp，见执行Tcl和控制台。',
        artifacts={n:dict(bytes=(current/n).stat().st_size,sha256=sha(current/n)) for n in files},
        prior_canonical_preserved=str(saved.relative_to(ROOT)),prior_export_snapshot='results/trials/baseline_initial')
    (current/'SOURCE_PROVENANCE.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FROZEN_BASELINE')

if __name__=='__main__':main()

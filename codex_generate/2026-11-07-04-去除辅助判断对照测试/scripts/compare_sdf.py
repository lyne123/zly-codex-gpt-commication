"""复用指定提交的AuxOn完整SDF证据，与NoAux比较全部输出及相同范围内事件。"""
from pathlib import Path
import json,hashlib
from analyze_sdf import read,write,stats
TASK=Path(__file__).resolve().parents[1]
OLD=TASK.parent/'2026-11-07-03-辅助跨帧匹配时序优化'
reference=OLD/'results/sdf/corrected/full'
candidate=TASK/'results/sdf/noaux/full'
scope=set(json.loads((TASK/'results/SCOPED_RTL_GATE.json').read_text(encoding='utf-8'))['scope_ids'])
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert load(reference/'RUN_MANIFEST.json')['completed'] and load(candidate/'RUN_MANIFEST.json')['completed']
assert load(reference/'RUN_MANIFEST.json')['stimulus_sha256']==load(candidate/'RUN_MANIFEST.json')['stimulus_sha256']
assert load(reference/'RUN_MANIFEST.json')['truth_sha256']==load(candidate/'RUN_MANIFEST.json')['truth_sha256']
assert load(reference.parent/'ANNOTATION.json')['DCP_sha256']=='01004b1502ef357304503269eaba73c9e41415456b58ecac76c393a53a6d9584'
assert load(reference.parent/'ANNOTATION.json')['corner']==load(candidate.parent/'ANNOTATION.json')['corner']=='slow/MAX'
assert sha(TASK/'inputs/frozen_compensation.csv')==sha(OLD/'inputs/frozen_compensation.csv')
sources={'aux_on':read(reference/'PULSE_RESULTS.csv'),'noaux':read(candidate/'PULSE_RESULTS.csv')}
sets={k:{int(r['event_id']):r for r in rows if r['status']=='MATCHED' and int(r['event_id']) in scope} for k,rows in sources.items()}
common=set(sets['aux_on']) & set(sets['noaux']);rows=[]
for mode,data in sources.items():
    for population in ['all_associated_outputs_including_mispairs','confirmed_correct_pairs','same_input_scope_common_ID']:
        if population=='all_associated_outputs_including_mispairs':selected=[r for r in data if r['error_ps']!='']
        elif population=='confirmed_correct_pairs':selected=[r for r in data if r['status']=='MATCHED']
        else:selected=[sets[mode][i] for i in sorted(common)]
        for group in ['all']+list(dict.fromkeys(r['case'] for r in selected)):
            group_rows=[r for r in selected if group=='all' or r['case']==group]
            rows.append(dict(mode=mode,population=population,group=group,
                             **stats(int(r['error_ps']) for r in group_rows)))
write(TASK/'results/SDF_COMPARISON.csv',rows,['mode','population','group','n','bias_ps','rmse_ps','std_sample_ps','std_population_ps','max_abs_ps'])
reference_info=dict(data_commit='d8b691b65316246567696cdbf8abd4e0f30950ee',
    source='codex_generate/2026-11-07-03-辅助跨帧匹配时序优化/results/sdf/corrected/full',
    reference_is_Corrected_AuxOn_not_production_A=True,
    simulator='XSim 2022.2',corner='slow/MAX',DCP_sha256=load(reference.parent/'ANNOTATION.json')['DCP_sha256'],
    original_stimulus_sha256=load(reference/'RUN_MANIFEST.json')['stimulus_sha256'],
    files={n:sha(reference/n) for n in ['RUN_MANIFEST.json','SUMMARY.json','PULSE_RESULTS.csv','EDGE_RESULTS.csv','candidate.csv','raw.csv','widths.csv','errors.csv','fifo.csv','error_fifo.csv','simulation.log.gz']},
    old_files_not_duplicated=True,reason='既有相同输入/参数/角的完整AuxOn SDF已完成，用不可变提交和校验引用，不重复运行或复制大型旧文件')
(TASK/'results/AUX_ON_SDF_REFERENCE.json').write_text(json.dumps(reference_info,ensure_ascii=False,indent=2),encoding='utf-8')
summary=dict(scope_expected=len(scope),aux_on_scope_correct=len(sets['aux_on']),NoAux_scope_correct=len(sets['noaux']),
    common_scope_input_events=len(common),NoAux_scope_missing=sorted(scope-set(sets['noaux'])),
    no_parameter_refit=True,no_outlier_removal=True,
    note='范围资格仅按原始输入时刻；全部关联输出的统计包括错配，正确配对子集另列，不能只展示子集制造改善',metrics=rows)
(TASK/'results/SDF_COMPARISON.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='metrics'},ensure_ascii=False,indent=2))

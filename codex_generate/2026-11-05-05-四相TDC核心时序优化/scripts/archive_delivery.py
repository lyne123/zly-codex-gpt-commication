"""归档本轮必要代码、原始CSV和时序证据；保留上一轮独立目录。"""
from pathlib import Path
import ast,csv,hashlib,json,re,shutil,subprocess

ROOT=Path('W:/');NAME='2026-11-05-05-四相TDC核心时序优化';TARGET=ROOT/'github/codex_generate'/NAME
PREVIOUS='2026-11-05-04-四相辅助检测与延迟补偿合并'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    v=json.loads((ROOT/'VALIDATION.json').read_text(encoding='utf-8'));assert v['status']=='PASS' and all(v['checks'].values())
    # 复现入口与本次已有编译日志原样保留，不重跑任何测试。
    shutil.copyfile(Path('Y:/scripts/register_ip.tcl'),ROOT/'scripts/register_ip.tcl')
    for source,label in [('rtl_baseline/compile.log','rtl_baseline_compile.log'),('rtl_compensated/compile.log','rtl_compensated_compile.log'),('locate_boundary/compile.log','locate_boundary_compile.log'),('unit/tb_wrap_equivalence_compile.log','wrap_equivalence_compile.log'),('unit/tb_fifo_reset_compile.log','fifo_reset_compile.log')]:
        shutil.copyfile(ROOT/'build'/source,ROOT/'logs'/label)
    files=[]
    for folder in ['rtl','original','sim','inputs','scripts']:
        files += [p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [p for p in (ROOT/'results').rglob('*') if p.is_file() and p.suffix in ['.csv','.json','.rpt','.txt','.log']]
    files += [ROOT/'results/compensated'/n for n in ['design.dcp','design.v','effective_constraints.xdc']]
    files += [p for p in (ROOT/'logs').glob('*') if p.is_file() and p.name not in ['build_console.log','GIT_PUBLICATION.json','ARCHIVE_CHECK.json','git_stage_review.log','git_commit.log','git_push.log','lfs_preupload.log','remote_branch_before.log']]
    files += [ROOT/n for n in ['RESULTS.md','TIMING_BEFORE_AFTER.md','RTL.diff','CORE_TIMING_PATHS.csv','VALIDATION.json','PLAN.md']]
    files=sorted(set(files));secret_pattern=re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}')
    for p in files:
        assert not re.search(r'(?i)(\.lic$|id_rsa$|\.pem$|\.key$|^\.env$)',p.name),p
        if p.suffix!='.dcp':assert not secret_pattern.search(p.read_text(encoding='utf-8',errors='replace')),('疑似敏感信息',p)
        if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8'))
    copied=[]
    for src in files:
        relative=src.relative_to(ROOT);dst=TARGET/relative;dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert sha(src)==sha(dst),('拒绝覆盖归档内容',dst)
        else:shutil.copyfile(src,dst)
        copied.append(dict(path=relative.as_posix(),bytes=src.stat().st_size,sha256=sha(src)))
    attributes='* -text\n'+''.join(f'results/compensated/{name} filter=lfs diff=lfs merge=lfs -text\n' for name in ['design.dcp','design.v'])
    (TARGET/'.gitattributes').write_text(attributes,encoding='utf-8')
    (ROOT/'.gitattributes').write_text(attributes,encoding='utf-8')
    # 索引仅追加本次与上一轮两行，已有索引内容逐字节保留。
    index=ROOT/'github/codex_generate/README.md';data=index.read_bytes();original=data
    for num,name,title in [('04',PREVIOUS,'四相辅助检测与延迟补偿合并'),('05',NAME,'四相TDC核心时序优化')]:
        assert name.encode() not in data
        eol=b'\r\n' if b'\r\n' in data else b'\n';row=f'| 2026-11-05-{num} | [{title}]({name}/RESULTS.md) |'.encode()
        previous=('03' if num=='04' else '04').encode();pos=data.index(b'\n',data.index(b'| 2026-11-05-'+previous+b' |'))+1
        data=data[:pos]+row+eol+data[pos:]
    stripped=data
    for num,name,title in [('04',PREVIOUS,'四相辅助检测与延迟补偿合并'),('05',NAME,'四相TDC核心时序优化')]:
        row=f'| 2026-11-05-{num} | [{title}]({name}/RESULTS.md) |'.encode();stripped=stripped.replace(row+eol,b'',1)
    assert stripped==original;index.write_bytes(data)
    names=sorted(p.relative_to(TARGET).as_posix() for p in TARGET.rglob('*') if p.is_file())
    listing='# 本轮文件清单\n\n原始CSV、测试平台、合并前后源码、时序报告、日志及最终DCP/网表均保留。工具缓存、中间检查点和重复console日志只保留本地，不重复推送。本轮无SDF或BIT。\n\n| 文件 | 字节 |\n|---|---:|\n'+''.join(f'| {n} | {(TARGET/n).stat().st_size} |\n' for n in names)
    (TARGET/'FILE_LIST.md').write_text(listing,encoding='utf-8')
    sums=''.join(f'{sha(p)}  {p.relative_to(TARGET).as_posix()}\n' for p in sorted(TARGET.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt')
    (TARGET/'SHA256SUMS.txt').write_text(sums,encoding='utf-8')
    for name in ['FILE_LIST.md','SHA256SUMS.txt']:shutil.copyfile(TARGET/name,ROOT/name)
    lfs=[]
    for task,extensions in [(PREVIOUS,['design.dcp','design.v','design.sdf']),(NAME,['design.dcp','design.v'])]:
        for name in extensions:
            p=ROOT/'github/codex_generate'/task/'results/compensated'/name
            lfs.append(dict(path=p.relative_to(ROOT/'github').as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
    (ROOT/'logs/LFS_PUBLICATION_OBJECTS.json').write_text(json.dumps(lfs,ensure_ascii=False,indent=2),encoding='utf-8')
    actual=[p for p in TARGET.rglob('*') if p.is_file()];previous=[p for p in (ROOT/'github/codex_generate'/PREVIOUS).rglob('*') if p.is_file()]
    status=dict(current_task_files=len(actual),previous_merge_files=len(previous),changed_index_files=1,total_new_files=len(actual)+len(previous),bytes_current=sum(p.stat().st_size for p in actual),bytes_previous=sum(p.stat().st_size for p in previous),LFS_objects=len(lfs),LFS_bytes=sum(p['bytes'] for p in lfs),max_file_bytes=max(p.stat().st_size for p in actual+previous),sensitive_matches=0,previous_merge_original_files_byte_identical=True)
    (ROOT/'logs/ARCHIVE_CHECK.json').write_text(json.dumps(status,indent=2),encoding='utf-8');print(json.dumps(status,indent=2))

if __name__=='__main__':main()

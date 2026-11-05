"""仅复制本轮必要证据到独立 Git 工作区，生成清单并检查来源完整性。"""
from pathlib import Path
import gzip
import hashlib
import json
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'2026-11-05-01-四相TDC时序优化与连续测量验证'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    # 按上一轮测量输出清单校验完整参照 CSV，禁止使用被改写的对照结果。
    frozen=OLD/'results/optimized/baseline/gate_validation'
    reference=json.loads((frozen/'raw_output_sha256.json').read_text())
    for name,meta in reference.items():
        p=frozen/name
        assert p.stat().st_size==meta['bytes'] and sha(p)==meta['sha256'],name
    shutil.copyfile(frozen/'raw_output_sha256.json',ROOT/'inputs/FROZEN_REFERENCE_SHA256.json')
    timing=[]
    for variant in ['baseline','compensated']:
        for name in ['fresh_timing_summary.rpt','module_worst_setup.csv','fresh_setup_top50.rpt']:
            p=OLD/'results/optimized'/variant/name
            timing.append(dict(source=str(p),sha256=sha(p),bytes=p.stat().st_size))
    (ROOT/'inputs/TIMING_SOURCE_REFERENCES.json').write_text(json.dumps(timing,ensure_ascii=False,indent=2),encoding='utf-8')
    before=json.loads((ROOT/'inputs/SOURCE_SHA256.json').read_text(encoding='utf-8'))
    assert all(sha(Path(p))==meta['sha256'] for p,meta in before.items()),'正式源码或冻结输入已变化'
    with gzip.open(ROOT/'logs/simulation.log.gz','rb') as f:compressed_sha=hashlib.file_digest(f,'sha256').hexdigest()
    assert compressed_sha==sha(ROOT/'results/short_baseline/simulation.log')
    files=[ROOT/n for n in ['FRONTEND_ROOT_CAUSE.md','EVENT_TRACE.csv','EVENT_DIAGNOSIS.csv']]
    for folder in ['scripts','sim','inputs']:files+=sorted((ROOT/folder).glob('*'))
    files+=sorted((ROOT/'results').glob('*.json'))+sorted((ROOT/'results').glob('*.csv'))
    files+=sorted((ROOT/'results/short_baseline').glob('*.csv'))
    files+=[ROOT/'logs'/n for n in ['compile_console.log','elaborate.log','simulation.log.gz','key_timing_warnings.log','COMPENSATED_LOCATE_SETUP_PATH.rpt','event_inspection.txt']]
    assert len(files)==len(set(files))
    suspect=[]
    patterns=[r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',r'ghp_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{30,}',r'AKIA[A-Z0-9]{16}']
    for p in files:
        if re.search(r'(?i)(?:^license|\.lic$|id_rsa$|\.pfx$|\.pem$|\.key$|^\.env$)',p.name):suspect.append(str(p))
        data=gzip.open(p,'rb').read() if p.suffix=='.gz' else p.read_bytes()
        content=data.decode('utf-8',errors='replace')
        for pattern in patterns:
            if re.search(pattern,content):suspect.append(str(p))
        assert p.stat().st_size<50*1024*1024,('需要另行评估大文件',p)
    assert not suspect,('疑似敏感文件，停止归档',suspect)
    target=ROOT/'github/codex_generate'/ROOT.name
    if target.exists():raise SystemExit('归档目录已经存在，拒绝覆盖；请先审查现有内容。')
    target.mkdir()
    for p in files:
        dest=target/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    (target/'.gitattributes').write_text('* -text\n',encoding='ascii')
    planned=sorted([p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()]+['FILE_LIST.md','SHA256SUMS.txt'])
    listing='# 本次归档文件清单\n\n共 '+str(len(planned))+' 个文件。旧任务大型实现文件按来源引用，不重复复制。\n\n'+'\n'.join(f'- [{n}]({n})' for n in planned)+'\n'
    (target/'FILE_LIST.md').write_text(listing,encoding='utf-8')
    actual=sorted(p for p in target.rglob('*') if p.is_file())
    sums=''.join(f'{sha(p)}  {p.relative_to(target).as_posix()}\n' for p in actual)
    (target/'SHA256SUMS.txt').write_text(sums,encoding='utf-8')
    for name in ['FILE_LIST.md','SHA256SUMS.txt']:shutil.copyfile(target/name,ROOT/name)
    index=ROOT/'github/codex_generate/README.md';data=index.read_bytes()
    assert ROOT.name.encode() not in data,'索引已经存在本任务，禁止重复追加'
    ending=b'\r\n' if b'\r\n' in data else b'\n'
    row=f'| 2026-11-05-02 | [四相TDC前端丢沿定位]({ROOT.name}/FRONTEND_ROOT_CAUSE.md) |'.encode('utf-8')
    marker='| 2026-11-05-01 |'.encode('utf-8');start=data.index(marker);pos=data.index(b'\n',start)+1
    updated=data[:pos]+row+ending+data[pos:]
    assert updated.replace(row+ending,b'',1)==data
    index.write_bytes(updated)
    result=dict(task_files=len(planned),task_bytes=sum(p.stat().st_size for p in target.rglob('*') if p.is_file()),max_file_bytes=max(p.stat().st_size for p in target.rglob('*') if p.is_file()),gzip_lossless=True,frozen_reference_hashes_verified=True,formal_sources_unchanged=True,sensitive_pattern_matches=0,old_implementation_files_duplicated=False)
    (ROOT/'logs/ARCHIVE_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

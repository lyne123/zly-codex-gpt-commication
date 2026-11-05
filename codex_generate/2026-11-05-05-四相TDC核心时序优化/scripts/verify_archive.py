"""保留原始字节并核验Git暂存对象；不修改任何实验数据或历史归档内容。"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess

ROOT=Path('W:/');NAME='2026-11-05-05-四相TDC核心时序优化';PREVIOUS='2026-11-05-04-四相辅助检测与延迟补偿合并'
REPO=ROOT/'github';TARGET=REPO/'codex_generate'/NAME
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(REPO),*args])
def refresh():
    # 索引沿用既有Git对象的换行，仅追加两行，避免工作区自动换行影响差异。
    index=REPO/'codex_generate/README.md';base=git('show','HEAD:codex_generate/README.md');current=index.read_bytes()
    stripped=current.replace(b'\r\n',b'\n')
    for num,name,title in [('04',PREVIOUS,'四相辅助检测与延迟补偿合并'),('05',NAME,'四相TDC核心时序优化')]:
        row=f'| 2026-11-05-{num} | [{title}]({name}/RESULTS.md) |'.encode();stripped=stripped.replace(row+b'\n',b'',1)
    assert stripped==base.replace(b'\r\n',b'\n'),'拒绝覆盖其他索引变更'
    canonical=base;eol=b'\r\n' if b'\r\n' in base else b'\n'
    for num,name,title in [('04',PREVIOUS,'四相辅助检测与延迟补偿合并'),('05',NAME,'四相TDC核心时序优化')]:
        row=f'| 2026-11-05-{num} | [{title}]({name}/RESULTS.md) |'.encode();preceding='03' if num=='04' else '04'
        pos=canonical.index(b'\n',canonical.index(f'| 2026-11-05-{preceding} |'.encode()))+1;canonical=canonical[:pos]+row+eol+canonical[pos:]
    index.write_bytes(canonical)
    # 首次归档后只允许更新本任务自有脚本；原始数据一旦不同即停止。
    previous={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (TARGET/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()}
    for source in (ROOT/'scripts').glob('*'):
        if source.suffix not in ['.py','.tcl']:continue
        dest=TARGET/'scripts'/source.name
        if dest.exists() and sha(source)!=sha(dest):assert previous.get(dest.relative_to(TARGET).as_posix())==sha(dest),dest
        shutil.copyfile(source,dest)
    for task,names in [(PREVIOUS,['design.dcp','design.v','design.sdf']),(NAME,['design.dcp','design.v'])]:
        attr='* -text\n'+''.join(f'results/compensated/{name} filter=lfs diff=lfs merge=lfs -text\n' for name in names)
        (REPO/'codex_generate'/task/'.gitattributes').write_text(attr,encoding='utf-8')
        if task==NAME:(ROOT/'.gitattributes').write_text(attr,encoding='utf-8')
    files=sorted(p for p in TARGET.rglob('*') if p.is_file() and p.name not in ['FILE_LIST.md','SHA256SUMS.txt'])
    listing='# 本轮文件清单\n\n原始CSV和日志按原始字节保留，两个新增任务目录均禁用Git换行转换。最终DCP/网表使用LFS；缓存、中间DCP和重复console日志保留本地。本轮没有SDF/BIT。\n\n| 文件 | 字节 |\n|---|---:|\n'+''.join(f'| {p.relative_to(TARGET).as_posix()} | {p.stat().st_size} |\n' for p in files)
    (TARGET/'FILE_LIST.md').write_text(listing,encoding='utf-8')
    (TARGET/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(TARGET).as_posix()}\n' for p in sorted(TARGET.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt'),encoding='utf-8')
    for name in ['FILE_LIST.md','SHA256SUMS.txt']:shutil.copyfile(TARGET/name,ROOT/name)
    print('ARCHIVE_METADATA_REFRESHED; experiment data unchanged')
def verify():
    lfs={r['path']:r for r in json.loads((ROOT/'logs/LFS_PUBLICATION_OBJECTS.json').read_text(encoding='utf-8'))}
    staged=git('diff','--cached','--name-status','-z').decode('utf-8').split('\0');staged=[x for x in staged if x]
    assert len(staged)%2==0;entries=list(zip(staged[::2],staged[1::2]))
    allowed=['codex_generate/'+PREVIOUS+'/','codex_generate/'+NAME+'/']
    assert all((status=='A' and any(path.startswith(p) for p in allowed)) or (status=='M' and path=='codex_generate/README.md') for status,path in entries)
    assert sum(status=='M' for status,path in entries)==1
    # 使用Git blob对象原始字节核对，避免仅检查工作区副本掩盖换行转换。
    raw=git('ls-files','--stage','-z').split(b'\0');objects={}
    for item in raw:
        if not item:continue
        header,path=item.split(b'\t',1);mode,oid,stage=header.split();path=path.decode('utf-8')
        if any(path.startswith(p) for p in allowed) or path=='codex_generate/README.md':objects[path]=oid.decode('ascii')
    proc=subprocess.Popen(['git','-C',str(REPO),'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    object_hashes={};count=0
    for path,oid in objects.items():
        if oid not in object_hashes:
            proc.stdin.write((oid+'\n').encode());proc.stdin.flush();header=proc.stdout.readline().split();size=int(header[2]);data=proc.stdout.read(size);assert proc.stdout.read(1)==b'\n';object_hashes[oid]=(hashlib.sha256(data).hexdigest(),data if path in lfs else None)
        digest,data=object_hashes[oid]
        if path in lfs:
            if data is None:
                data=git('cat-file','blob',oid)
            text=data.decode('ascii');r=lfs[path]
            assert text.startswith('version https://git-lfs.github.com/spec/v1\n') and f"oid sha256:{r['sha256']}\n" in text and f"size {r['bytes']}\n" in text,path
            obj=REPO/'.git/lfs/objects'/r['sha256'][:2]/r['sha256'][2:4]/r['sha256'];assert sha(obj)==r['sha256']
        else:assert digest==sha(REPO/path),('Git暂存字节与原文件不同',path)
        count+=1
    proc.stdin.close();assert proc.wait()==0
    for task in [PREVIOUS,NAME]:
        folder=REPO/'codex_generate'/task
        for line in (folder/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
            digest,name=line.split('  ',1);assert sha(folder/name)==digest,(task,name)
    previous=json.loads((ROOT/'inputs/PRESERVED_MERGE.json').read_text(encoding='utf-8'))
    for item in previous['files']:assert sha(REPO/'codex_generate'/PREVIOUS/item['path'])==item['sha256']
    assert git('rev-parse','HEAD').decode().strip()=='6b341d88497541f23eaefee1cfad4e4925c7f2aa'
    result=dict(staged_paths=len(entries),new_files=sum(s=='A' for s,p in entries),modified_files=1,deletions=0,raw_blob_checks=count,LFS_objects=len(lfs),LFS_objects_sha256_verified=True,all_original_file_bytes_preserved=True,previous_merge_234_files_byte_identical=True,current_task_files=sum(p.startswith(allowed[1]) for s,p in entries),previous_merge_files=sum(p.startswith(allowed[0]) for s,p in entries),sensitive_files=0)
    (ROOT/'logs/GIT_STAGE_VERIFICATION.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['refresh','verify']);a=p.parse_args()
    refresh() if a.action=='refresh' else verify()

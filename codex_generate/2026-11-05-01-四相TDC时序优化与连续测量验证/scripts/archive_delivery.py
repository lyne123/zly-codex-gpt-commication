"""复制本任务证据到独立Git工作树；大日志无损压缩，原文件保持。"""
from pathlib import Path
import csv
import gzip
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'github/codex_generate'/ROOT.name

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    assert (ROOT/'results/final_acceptance.json').exists(),'先完成实验和报告'
    assert not DEST.exists(),'拒绝覆盖已建立交付目录'
    selected=[]
    for folder in ['inputs','original','rtl','sim','scripts','logs','results']:
        for p in (ROOT/folder).rglob('*'):
            if not p.is_file() or '__pycache__' in p.parts:continue
            # 旧缓存备选未用于最终实现，保留唯一实际验证的Debug Hub缓存。
            if 'prebuilt_debug_hub_cache' in p.parts:continue
            selected.append(p)
    selected += [p for p in ROOT.iterdir() if p.is_file() and p.suffix in {'.md','.patch','.csv','.txt'} and p.name!='WORK_STATE.md']
    # 工程和原生执行/失败日志保留；对象、波形和可重新生成的批量缓存不归档。
    native_ext={'.log','.jou','.rpt','.tcl','.xpr','.prj','.bat','.ps1','.xci','.xdc','.sv','.vh','.dmp'}
    selected += [p for p in (ROOT/'build').rglob('*') if p.is_file() and p.suffix.lower() in native_ext and not any(x in p.parts for x in ['shared_ip_cache','.Xil','xsim.dir'])]
    records=[]
    for source in sorted(set(selected)):
        relative=source.relative_to(ROOT)
        target=DEST/relative
        compressed=source.suffix.lower() in {'.log','.jou'} and source.stat().st_size>5*1024*1024
        if compressed:target=target.with_name(target.name+'.gz')
        target.parent.mkdir(parents=True,exist_ok=True)
        if compressed:
            with source.open('rb') as src, target.open('wb') as raw:
                with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as dst:shutil.copyfileobj(src,dst)
            with gzip.open(target,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==sha(source)
        else:
            shutil.copyfile(source,target)
            assert sha(source)==sha(target)
        records.append(dict(source=relative.as_posix(),archived=target.relative_to(DEST).as_posix(),source_bytes=source.stat().st_size,source_sha256=sha(source),archived_bytes=target.stat().st_size,archived_sha256=sha(target),storage='gzip_lossless' if compressed else 'copy'))
    with (DEST/'ARCHIVE_MAPPING.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=records[0].keys());writer.writeheader();writer.writerows(records)
    # 全任务关闭换行归一化，防止Git修改原始CSV/日志字节及SHA。
    attrs=['* -text','*.bit filter=lfs diff=lfs merge=lfs -text','*.dcp filter=lfs diff=lfs merge=lfs -text','*.sdf filter=lfs diff=lfs merge=lfs -text','results/**/design.v filter=lfs diff=lfs merge=lfs -text']
    attrs += [r['archived']+' filter=lfs diff=lfs merge=lfs -text' for r in records if r['archived_bytes']>20*1024*1024 and not r['archived'].endswith(('.bit','.dcp','.sdf'))]
    (DEST/'.gitattributes').write_text('\n'.join(attrs)+'\n',encoding='utf-8')
    files={p.relative_to(DEST).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(DEST.rglob('*')) if p.is_file()}
    (DEST/'SHA256_MANIFEST.json').write_text(json.dumps(dict(algorithm='SHA256',note='清单本身不作递归自哈希；gzip可依ARCHIVE_MAPPING恢复并验证原SHA',files=files),ensure_ascii=False,indent=2),encoding='utf-8')
    with (DEST/'FILE_LIST.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['file','bytes','sha256'])
        writer.writerows((p,r['bytes'],r['sha256']) for p,r in files.items())
    print(json.dumps(dict(directory=str(DEST),files=len(files)+2,bytes=sum(r['bytes'] for r in files.values())),ensure_ascii=False))

if __name__=='__main__':main()

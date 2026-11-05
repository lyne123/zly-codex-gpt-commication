"""按原字节复制本次实现产物，先暂存LFS对象，不提前发布未完成报告。"""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path('W:/');NAME='2026-11-05-03-四相TDC辅助边沿检测优化'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    target=ROOT/'github/codex_generate'/NAME;target.mkdir(parents=True,exist_ok=True)
    attrs='* -text\nresults/baseline/*.bit filter=lfs diff=lfs merge=lfs -text\nresults/baseline/*.dcp filter=lfs diff=lfs merge=lfs -text\nresults/baseline/*.sdf filter=lfs diff=lfs merge=lfs -text\nresults/baseline/design.v filter=lfs diff=lfs merge=lfs -text\n'
    if (target/'.gitattributes').exists():assert (target/'.gitattributes').read_text()==attrs
    else:(target/'.gitattributes').write_bytes(attrs.encode())
    records=[]
    for name in ['Baseline_Aux4Phase.bit','design.dcp','design.sdf','design.v']:
        source=ROOT/'results/baseline'/name;dest=target/'results/baseline'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert sha(dest)==sha(source)
        else:shutil.copyfile(source,dest)
        records.append(dict(path=(dest.relative_to(ROOT/'github')).as_posix(),bytes=source.stat().st_size,oid=sha(source)))
    (ROOT/'inputs/LFS_OBJECTS.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print('LFS_READY',len(records),sum(r['bytes'] for r in records),'bytes')
if __name__=='__main__':main()

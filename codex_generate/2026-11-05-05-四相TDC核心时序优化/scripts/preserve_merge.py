"""将上一轮未推送的交付逐文件原样归档，独立于本轮优化目录。"""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path('W:/');PREVIOUS=Path('Y:/')
NAME='2026-11-05-04-四相辅助检测与延迟补偿合并'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    target=ROOT/'github/codex_generate'/NAME;preserved=[]
    rows=[line.split('  ',1) for line in (PREVIOUS/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()]
    rows += [(sha(PREVIOUS/name),name) for name in ['FILE_LIST.md','SHA256SUMS.txt']]
    for digest,name in rows:
        src=PREVIOUS/name;dst=target/name;assert sha(src)==digest,name
        dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert sha(dst)==digest,('拒绝覆盖不同内容',dst)
        else:shutil.copyfile(src,dst)
        assert sha(dst)==digest;preserved.append(dict(path=name,bytes=src.stat().st_size,sha256=digest))
    # 只新增归档管理属性，不改动上一轮任何源码、测量、报告或日志字节。
    (target/'.gitattributes').write_text('* -text\n'+''.join(f'results/compensated/{name} filter=lfs diff=lfs merge=lfs -text\n' for name in ['design.dcp','design.v','design.sdf']),encoding='utf-8')
    (ROOT/'inputs/PRESERVED_MERGE.json').write_text(json.dumps(dict(source='Y:/',archive_path='codex_generate/'+NAME,all_experiment_bytes_preserved=True,files=preserved,archive_only_added_file='.gitattributes'),ensure_ascii=False,indent=2),encoding='utf-8')
    print('PREVIOUS_MERGE_PRESERVED',len(preserved),'files; original FAIL kept')

if __name__=='__main__':main()

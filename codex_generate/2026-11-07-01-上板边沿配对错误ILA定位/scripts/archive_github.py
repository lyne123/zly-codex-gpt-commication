"""仅向独立worktree增加本次交付及索引；检查文件散列和敏感内容。"""
from pathlib import Path
import hashlib,json,re,shutil,sys
TASK=Path(__file__).resolve().parents[1]
REPO=TASK/'github'
DEST=REPO/'codex_generate'/TASK.name
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    assert (REPO/'.git').is_file(),'不是本次独立worktree'
    update='--update-current' in sys.argv
    assert not DEST.exists() or update,'已有本任务归档，继续工作需显式使用--update-current'
    checked=0
    for line in (TASK/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1);assert sha(TASK/name)==digest,name;checked+=1
    files=sorted(p for p in TASK.rglob('*') if p.is_file() and 'github' not in p.relative_to(TASK).parts and '__pycache__' not in p.parts and p.name!='GIT_DELIVERY.json')
    sensitive=re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\bghp_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}')
    for p in files:
        assert p.suffix.lower() not in {'.lic','.pem','.pfx'},p
        if p.suffix.lower() in {'.md','.json','.tcl','.py','.v','.vh','.sv','.xdc','.log','.jou','.txt','.csv'}:
            assert not sensitive.search(p.read_bytes()),f'疑似敏感内容: {p}'
        assert p.stat().st_size<100*1024*1024,p
    for p in files:
        dst=DEST/p.relative_to(TASK);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
        assert sha(dst)==sha(p)
    index=REPO/'codex_generate/README.md'
    entry=f'\n2026-11-07-01：[上板边沿配对错误ILA定位]({TASK.name}/RESULTS.md)。\n'
    if TASK.name not in index.read_text(encoding='utf-8'):
        with index.open('a',encoding='utf-8') as f:f.write(entry)
    print(json.dumps(dict(files=len(files),bytes=sum(p.stat().st_size for p in files),sha_verified=checked,
        sensitive_scan='PASS',old_task_files_modified=False,destination=str(DEST)),ensure_ascii=False))
if __name__=='__main__':main()

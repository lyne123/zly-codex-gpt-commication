"""仅归档本任务及追加索引；冻结证据逐字节复制，检查敏感项与LFS文件。"""
from pathlib import Path
import hashlib,json,re,shutil
TASK=Path(__file__).resolve().parents[1];REPO=TASK/'github';ROOT=TASK.parents[1]
NAME=TASK.name;DEST=REPO/'codex_generate'/NAME
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def payload():
    return sorted(p for p in TASK.rglob('*') if p.is_file() and not any(x in {'github','__pycache__'} for x in p.relative_to(TASK).parts) and p.name not in {'SHA256SUMS.txt','FILE_LIST.txt'})
assert not DEST.exists(),'目标任务已经存在，禁止覆盖'
assert json.loads((TASK/'results/VALIDATION.json').read_text(encoding='utf-8'))['formal_RTL_modified'] is False
patterns=[re.compile(x) for x in [r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',r'\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_]{20,}',r'\bAKIA[A-Z0-9]{16}\b']]
bad=[];largest=[]
for p in payload():
    rel=p.relative_to(TASK).as_posix();largest.append((p.stat().st_size,rel))
    if p.suffix.lower() in {'.lic','.pem','.key','.pfx'} or p.name in {'id_rsa','id_ed25519','.env','license.dat'}:bad.append(rel)
    if p.suffix.lower() not in {'.dcp','.bit'}:
        # 扫描真实凭证样式；扫描器自身的正则文本不会匹配成真实密钥。
        text=p.read_text(encoding='utf-8',errors='replace')
        if any(rule.search(text) for rule in patterns):bad.append(rel)
assert not bad,sorted(set(bad))
assert not any(size>=100*1024*1024 for size,name in largest),'存在需要单独确认的普通Git大文件'
audit=dict(sensitive_file_or_token_findings=[],largest_files=[dict(path=n,bytes=s) for s,n in sorted(largest,reverse=True)[:10]],
    LFS_extensions=['.dcp','.sdf','.bit'],raw_files_changed=False,excluded=['github工作树及Git元数据','Python __pycache__','真实ASCII运行目录中的OOC缓存和中间综合/布局DCP'],
    current_evidence_omitted=[],old_reference_locations='inputs/EXTERNAL_REFERENCES.json')
(TASK/'results/ARCHIVE_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
paths=payload();names=[p.relative_to(TASK).as_posix() for p in paths]+['FILE_LIST.txt','SHA256SUMS.txt']
(TASK/'FILE_LIST.txt').write_text('\n'.join(sorted(names))+'\n',encoding='utf-8')
paths.append(TASK/'FILE_LIST.txt')
(TASK/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(TASK).as_posix()}\n' for p in sorted(paths)),encoding='utf-8')
paths.append(TASK/'SHA256SUMS.txt')
for p in paths:
    dst=DEST/p.relative_to(TASK);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
    assert sha(p)==sha(dst),str(p)
index=REPO/'codex_generate/README.md';old=index.read_bytes()
assert NAME.encode('utf-8') not in old
addition=f'\n2026-11-07-02：[辅助下降沿跨帧匹配验证]({NAME}/README.md)。\n'.encode('utf-8')
index.write_bytes(old+addition);assert index.read_bytes().startswith(old)
print(json.dumps(dict(task_files=len(paths),total_bytes=sum(p.stat().st_size for p in paths),worktree=str(REPO),copied_byte_exact=True,history_deleted=False),ensure_ascii=False))

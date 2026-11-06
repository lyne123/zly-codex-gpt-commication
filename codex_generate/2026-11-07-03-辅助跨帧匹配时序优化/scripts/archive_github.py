"""只复制本次任务及追加索引；生成文件清单，Git提交与推送另行检查执行。"""
from pathlib import Path
import csv,hashlib,json,re,shutil

TASK=Path(__file__).resolve().parents[1];REPO=TASK/'github'
assert json.loads((TASK/'VALIDATION.json').read_text(encoding='utf-8'))['archive_ready']
DEST=REPO/'codex_generate'/TASK.name
assert not DEST.exists(),'不覆盖已有任务'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def payload():
    # 不遍历嵌套历史仓库、解释器缓存，也不打包自身生成的清单。
    for folder in TASK.iterdir():
        if folder.name in ['github','__pycache__','SHA256SUMS.txt','FILE_LIST.csv']:continue
        if folder.is_file():yield folder
        elif folder.is_dir():
            for p in folder.rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts:yield p

secret=re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{30,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}')
files=list(payload())
for p in files:
    assert p.name.lower() not in ['id_rsa','id_ed25519','license.lic','.env'],str(p)
    if p.suffix.lower() not in ['.bit','.dcp','.gz']:
        assert not secret.search(p.read_bytes()),'疑似敏感材料：'+str(p)
    assert p.stat().st_size<100*1024*1024 or p.suffix.lower() in ['.bit','.dcp','.sdf'],'需先配置大文件管理'
audit=dict(pass_all=True,scope='仅本次任务和索引追加',secret_pattern_matches=0,
    excluded=['github/','__pycache__/','Vivado临时缓存','重复中间DCP'],
    maximum_file_size=max(p.stat().st_size for p in files),old_task_deleted=False,
    no_critical_evidence_omitted=True,files_not_uploaded_for_size=[])
(TASK/'results/ARCHIVE_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
files=sorted(payload(),key=lambda p:p.relative_to(TASK).as_posix())
records=[dict(path=p.relative_to(TASK).as_posix(),size=p.stat().st_size,sha256=sha(p)) for p in files]
with (TASK/'FILE_LIST.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['path','size','sha256']);w.writeheader();w.writerows(records)
(TASK/'SHA256SUMS.txt').write_text(''.join(f"{r['sha256']}  {r['path']}\n" for r in records),encoding='utf-8')
for p in files+[TASK/'FILE_LIST.csv',TASK/'SHA256SUMS.txt']:
    target=DEST/p.relative_to(TASK);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    assert sha(p)==sha(target)
index=REPO/'codex_generate/README.md'
old=index.read_bytes()
line=f'\n2026-11-07-03：[辅助跨帧匹配时序优化]({TASK.name}/README.md)。\n'.encode('utf-8')
assert TASK.name.encode('utf-8') not in old,'已有本任务索引，不重复追加'
index.write_bytes(old+line)
print('ARCHIVE_COPIED',len(files)+2,'files; index append only; no commit or push yet',flush=True)

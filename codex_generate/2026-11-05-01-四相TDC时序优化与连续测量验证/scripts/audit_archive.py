"""核对交付SHA、凭据模式及Git实际暂存字节；不输出匹配到的敏感值。"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT/'github'
TASK=Path('codex_generate')/ROOT.name
DEST=REPO/TASK
PATTERNS={
    'private_key':rb'-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----',
    'github_token':rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})',
    'openai_key':rb'sk-(?:proj|svcacct)-[A-Za-z0-9_-]{20,}',
    'aws_access_key':rb'AKIA[0-9A-Z]{16}',
    'license_feature':rb'(?m)^(?:FEATURE|INCREMENT)\s+\S+\s+xilinxd\s+',
}

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def scan(stream,name,findings):
    tail=b''
    while block:=stream.read(1024*1024):
        data=tail+block
        for label,pattern in PATTERNS.items():
            if re.search(pattern,data) or re.search(pattern,data.replace(b'\0',b'')):
                findings.append(dict(file=name,kind=label))
        tail=data[-512:]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--git-index',action='store_true');args=parser.parse_args()
    files=sorted(p for p in DEST.rglob('*') if p.is_file())
    manifest=json.loads((DEST/'SHA256_MANIFEST.json').read_text(encoding='utf-8'))['files']
    assert {p.relative_to(DEST).as_posix() for p in files}==set(manifest)|{'SHA256_MANIFEST.json','FILE_LIST.csv'}
    for name,r in manifest.items():
        p=DEST/name;assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],name
    findings=[]
    for p in files:
        name=p.relative_to(DEST).as_posix()
        if p.suffix.lower() in {'.lic','.pem','.pfx','.key'} or p.name in {'id_rsa','id_ed25519','.env'}:
            findings.append(dict(file=name,kind='sensitive_filename'))
        if p.suffix=='.gz':
            with gzip.open(p,'rb') as stream:scan(stream,name,findings)
        elif p.suffix=='.dcp' and zipfile.is_zipfile(p):
            with zipfile.ZipFile(p) as archive:
                for member in archive.infolist():
                    if member.is_dir():continue
                    with archive.open(member) as stream:scan(stream,name+'!'+member.filename,findings)
        else:
            with p.open('rb') as stream:scan(stream,name,findings)
    result=dict(files=len(files),manifest_verified=True,sensitive_findings=findings)
    assert not findings,json.dumps(findings,ensure_ascii=False)
    if args.git_index:
        staged=subprocess.check_output(['git','-C',str(REPO),'ls-files','--stage','-z','--',TASK.as_posix()+'/'])
        entries=[]
        for row in staged.split(b'\0'):
            if not row:continue
            info,path=row.split(b'\t',1);mode,oid,stage=info.split()
            assert stage==b'0' and mode in {b'100644',b'100755'}
            entries.append((oid,path.decode('utf-8')))
        assert len(entries)==len(files)
        process=subprocess.Popen(['git','-C',str(REPO),'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
        lfs=0
        for oid,path in entries:
            process.stdin.write(oid+b'\n');process.stdin.flush()
            header=process.stdout.readline().split();assert header[1]==b'blob'
            body=process.stdout.read(int(header[2]));assert process.stdout.read(1)==b'\n'
            local=REPO/path;digest=sha(local)
            pointer=re.search(rb'^oid sha256:([a-f0-9]{64})$',body,re.M) if body.startswith(b'version https://git-lfs.github.com/spec/v1\n') else None
            if pointer:
                assert pointer[1].decode()==digest,path
                assert int(re.search(rb'^size (\d+)$',body,re.M)[1])==local.stat().st_size,path
                lfs+=1
            else:
                assert hashlib.sha256(body).hexdigest()==digest,'Git转换了原始字节：'+path
                assert local.suffix.lower() not in {'.bit','.dcp','.sdf'},'关键实现文件未使用LFS：'+path
        process.stdin.close();assert process.wait()==0
        result.update(git_index_byte_equivalence_verified=True,git_index_files=len(entries),lfs_pointer_files=lfs)
    name='GIT_INDEX_VERIFICATION.json' if args.git_index else 'ARCHIVE_VERIFICATION.json'
    (ROOT/'logs'/name).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()

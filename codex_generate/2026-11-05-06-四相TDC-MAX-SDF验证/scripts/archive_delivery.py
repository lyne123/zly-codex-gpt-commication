"""仅复制本轮证据到独立Git分支；原始大日志无损压缩，不改动实验结果。"""
from pathlib import Path
import ast, gzip, hashlib, json, re, shutil, subprocess

ROOT = Path('Z:/')
NAME = '2026-11-05-06-四相TDC-MAX-SDF验证'
REPO = ROOT / 'github'
DEST = REPO / 'codex_generate' / NAME
BASE = 'ba978229094a8621b30770177727d8e70b831a74'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    assert subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip() == BASE
    assert subprocess.check_output(['git', '-C', str(REPO), 'branch', '--show-current'], text=True).strip() == 'codex/2026-11-05-06-tdc-max-sdf-validation'
    assert not DEST.exists(), '禁止覆盖已有任务归档'
    for path in (ROOT / 'scripts').glob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    manifest = json.loads((ROOT / 'inputs/LOG_COMPRESSION_MANIFEST.json').read_text(encoding='utf-8'))
    originals = {Path(row['original']) for row in manifest}
    # 补充全部ModelSim失败日志和完整控制台输出，逐字节检查解压结果。
    for path in sorted((ROOT / 'logs').glob('*.log')) + [ROOT / 'results/compensated/gate_full/console.log']:
        if path.stat().st_size <= 1000000 or path in originals:
            continue
        compressed = Path(str(path) + '.gz')
        with path.open('rb') as source, gzip.open(compressed, 'wb', compresslevel=6) as target:
            shutil.copyfileobj(source, target)
        manifest.append(dict(original=str(path), original_bytes=path.stat().st_size,
                             compressed=str(compressed), compressed_bytes=compressed.stat().st_size,
                             uncompressed_sha256=sha(path)))
        originals.add(path)
    for row in manifest:
        path = Path(row['original'])
        assert sha(path) == row['uncompressed_sha256']
        with gzip.open(row['compressed'], 'rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['uncompressed_sha256']
        row['archive_compressed_path'] = Path(row['compressed']).relative_to(ROOT).as_posix()
        row['original_local_full_path'] = str(Path('D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/codex_generate') / NAME / path.relative_to(ROOT))
    (ROOT / 'inputs/LOG_COMPRESSION_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    selected = []
    excluded = []
    for directory in ['inputs', 'scripts', 'sim', 'netlist', 'plots', 'logs', 'results']:
        for path in (ROOT / directory).rglob('*'):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            reason = None
            if '__pycache__' in path.parts or path.suffix in ('.pyc', '.pb', '.csd'):
                reason = '工具缓存/可再生中间文件'
            elif path.name.startswith('modelsim_manual_') or path.name == 'manual_reader_install.log':
                reason = '商业手册参考摘录或其阅读器安装记录，不属于实验数据'
            elif path in originals:
                reason = '全部字节已无损gzip归档，原件本地保留；见LOG_COMPRESSION_MANIFEST.json'
            elif '.backup.' in path.name:
                reason = '与已保存失败日志重复的工具自动备份'
            elif directory == 'results' and len(path.relative_to(ROOT / 'results').parts) > 1 and path.relative_to(ROOT / 'results').parts[0] != 'compensated' and path.name != 'RUN_COMMAND.json':
                reason = '零时刻注释探针的空结果/重复激励；失败命令和全部注释日志已保存'
            if reason:
                excluded.append(dict(path=relative, bytes=path.stat().st_size, reason=reason))
            else:
                selected.append(path)
    selected += [ROOT / name for name in ['README.md', 'REPRODUCE.md', 'SDF_VALIDATION.md', 'VALIDATION.json']]
    # 不归档编译库、商业工具、旧大DCP或Git克隆；旧04/05目录保持父提交内容。
    selection = dict(archive_task=NAME, parent_commit=BASE, excluded_files=excluded,
                     excluded_trees={'build/': '可再生编译缓存/工具库/阅读器，不包含实验原始结果',
                                     'github/': '独立Git克隆本身，不递归归档'},
                     critical_evidence_omitted=False,
                     compression_note='gzip无损恢复原始全部字节；没有删行或修改CSV/日志')
    (ROOT / 'ARCHIVE_SELECTION.json').write_text(json.dumps(selection, ensure_ascii=False, indent=2), encoding='utf-8')
    selected.append(ROOT / 'ARCHIVE_SELECTION.json')
    patterns = [rb'ghp_[A-Za-z0-9]{30,}', rb'github_pat_[A-Za-z0-9_]{30,}',
                rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----', rb'AKIA[A-Z0-9]{16}']
    for path in selected:
        assert path.suffix.lower() not in ('.lic', '.pem', '.key', '.pfx'), path.name
        if path.suffix.lower() not in ('.gz', '.png'):
            content = path.read_bytes()
            assert not any(re.search(pattern, content) for pattern in patterns), '疑似敏感凭证：' + str(path)
    DEST.mkdir(parents=True)
    for path in selected:
        target = DEST / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        assert sha(path) == sha(target)
    # 禁止autocrlf改写原始CSV/日志；大文件用LFS保持内容哈希。
    lfs = [path.relative_to(DEST).as_posix() for path in DEST.rglob('*') if path.is_file() and
           (path.stat().st_size >= 1000000 or path.suffix == '.sdf')]
    attributes = '* -text\n' + ''.join(f'{name} filter=lfs diff=lfs merge=lfs -text\n' for name in sorted(lfs))
    (DEST / '.gitattributes').write_text(attributes, encoding='utf-8')
    files = sorted(path for path in DEST.rglob('*') if path.is_file())
    # 两个清单避免循环自校验；SHA清单覆盖FILE_LIST，但不覆盖自身。
    rows = ['# 本轮实际上传文件清单', '', '所有原始大日志的gzip映射见inputs/LOG_COMPRESSION_MANIFEST.json。', '',
            '| 文件 | 字节数 | 存储 |', '|---|---:|---|']
    for path in files:
        name = path.relative_to(DEST).as_posix()
        rows.append(f'| {name} | {path.stat().st_size} | {"Git LFS" if name in lfs else "Git"} |')
    rows += ['| FILE_LIST.md | 自列清单 | Git |', '| SHA256SUMS.txt | 校验清单 | Git |', '',
             f'实际文件数：{len(files) + 2}；LFS文件数：{len(lfs)}。',
             'SHA256SUMS覆盖除自身外的全部归档文件；旧DCP/RTL/BIT继续引用父提交，不重复上传。', '']
    (DEST / 'FILE_LIST.md').write_text('\n'.join(rows), encoding='utf-8')
    files = sorted(path for path in DEST.rglob('*') if path.is_file())
    sums = ''.join(f'{sha(path)}  {path.relative_to(DEST).as_posix()}\n' for path in files)
    (DEST / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8')
    for name in ['.gitattributes', 'FILE_LIST.md', 'SHA256SUMS.txt']:
        shutil.copyfile(DEST / name, ROOT / name)
    # 从原Git blob追加单行，不让工作副本换行转换影响已有索引内容。
    data = subprocess.check_output(['git', '-C', str(REPO), 'show', BASE + ':codex_generate/README.md'])
    assert NAME.encode('utf-8') not in data
    eol = b'\r\n' if b'\r\n' in data else b'\n'
    marker = b'| 2026-11-05-05 |'
    pos = data.index(b'\n', data.index(marker)) + 1
    row = f'| 2026-11-05-06 | [四相TDC-MAX-SDF验证]({NAME}/SDF_VALIDATION.md) |'.encode('utf-8') + eol
    (REPO / 'codex_generate/README.md').write_bytes(data[:pos] + row + data[pos:])
    result = dict(files=len(files) + 1, total_bytes=sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file()),
                  lfs_files=len(lfs), archive=str(DEST), no_critical_evidence_omitted=True,
                  secret_pattern_scan='PASS', python_AST='PASS', lossless_compressed_files=len(manifest))
    (ROOT / 'build/archive_preflight.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

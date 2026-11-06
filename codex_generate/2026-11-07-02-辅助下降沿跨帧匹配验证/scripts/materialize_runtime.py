"""从归档副本恢复本任务ASCII运行目录；不修改正式工程，不覆盖已有仿真结果。"""
from pathlib import Path
import shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02'
WORK.mkdir(parents=True,exist_ok=True)
for variant in (TASK/'variants').iterdir():
    if variant.is_dir():
        dest=WORK/variant.name
        for source in (TASK/'original/rtl').glob('*.v'):
            target=dest/source.name;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():shutil.copy2(source,target)
        for source in variant.glob('*.v'):
            target=dest/source.name
            if target.exists() and target.read_bytes()!=source.read_bytes():
                if (WORK/(variant.name+'.vvp')).exists():raise RuntimeError('已有运行版本不同，禁止覆盖')
            shutil.copy2(source,target)
shutil.copytree(TASK/'sim',WORK/'sim',dirs_exist_ok=True)
print('REAL_ASCII_RUNTIME=',WORK)

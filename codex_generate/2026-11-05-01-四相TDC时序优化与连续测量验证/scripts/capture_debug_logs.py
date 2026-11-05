"""在Vivado自动清理嵌套IP工程前保存其日志与配置，只观察本次临时目录。"""
from pathlib import Path
import time
import shutil

root=Path('U:/')
source=root/'build/baseline/timing_baseline.runs/impl_1/.Xil'
dest=root/'logs/debug_capture'
seen={};start=time.monotonic()
while time.monotonic()-start<900 and not (root/'build/STOP_DEBUG_WATCH').exists():
    if source.exists():
        for f in source.rglob('*'):
            if f.suffix not in {'.log','.vds','.jou','.tcl','.xpr','.xci','.pb'}:continue
            try:
                st=f.stat();key=(st.st_mtime_ns,st.st_size)
                if not f.is_file() or seen.get(f)==key:continue
                target=dest/f.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(f,target);seen[f]=key
            except (OSError,FileNotFoundError):pass
    time.sleep(1)
print('DEBUG_CAPTURE_FILES',len(seen),flush=True)

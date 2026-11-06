"""用交付包中的源码/IP配置，在新的ASCII目录准备复现；不依赖盘符映射。"""
from pathlib import Path
import shutil,sys
task=Path(__file__).resolve().parents[1]
work=Path(sys.argv[1]).resolve()
assert work.as_posix().isascii(),'Vivado 2022.2运行目录需为真实ASCII路径'
assert not work.exists(),'请使用尚不存在的新目录，禁止覆盖旧结果'
work.mkdir(parents=True)
shutil.copytree(task/'rtl',work/'rtl')
for name in ['compensation_params.tcl','combine_AD23.xdc','production_AD23.dcp']:
    shutil.copy2(task/'inputs'/name,work/name)
for name in ['clk_wiz_0','fifo_tdc_result','ila_3']:
    dst=work/'registered/aux_compensated.srcs/sources_1/ip'/name
    dst.mkdir(parents=True)
    shutil.copy2(task/'inputs/ip'/name/(name+'.xci'),dst/(name+'.xci'))
(work/'ip_cache').mkdir()
shutil.copy2(task/'scripts/build_debug.tcl',work/'build_debug.tcl')
print('REVIEW_WORKSPACE_READY',work)

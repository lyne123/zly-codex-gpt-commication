# 位流版本对应

| 版本 | 位流 | DCP | RTL | 参数 |
|---|---|---|---|---|
| Baseline | Baseline.bit | results/baseline/design.dcp | ../01_RTL/before/rtl/ 五文件 | 原始无补偿 |
| Compensated | Compensated.bit | results/compensated/design.dcp | ../01_RTL/after/ 五文件 | ../03_Calibration/results/calibration_params.tcl，ENABLE_SKEW_COMP=1 |

精确哈希、器件、工具与激励版本见 ../06_Timing/results/{baseline,compensated}/version_manifest.json 以及FILE_INDEX。生成日志均映射到05_Results；没有上板烧写。

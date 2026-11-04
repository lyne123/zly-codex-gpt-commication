# 日志位置

SDF注释与警告原文、综合实现和失败尝试日志统一存放05_Results，逐路径定位见根目录FILE_INDEX.csv。关键路径包括 `results/<版本>/gate_validation/{elaboration,simulation}.log`，`logs/` 下控制台日志，以及 `build/` 下runme.log、Vivado日志和journal。

本目录保存路由后报告、注释实际网表/SDF和sdf_audit.json。64个CARRY4、256个采样FF及7个LUT1关键清单齐全；没有工具提供的全局逐路径注释百分比，不虚构该成功率。

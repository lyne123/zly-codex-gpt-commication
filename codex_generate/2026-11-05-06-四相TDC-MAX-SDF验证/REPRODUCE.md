# 复现与证据读取

本轮实际使用Vivado/XSim 2022.2，500 MHz四相时钟，Slow/MAX，1 ps分辨率。先尝试ModelSim SE-64 2020.4，因互连和负时序检查兼容性未接受其注释，失败记录完整保留；没有转用Questa 2026.1，也没有用理想RTL代替SDF。

## 独立重放已冻结网表

1. 克隆本分支并执行`git lfs pull`，确认SDF/网表已经下载为真实内容而非LFS指针。用`SHA256SUMS.txt`核对归档文件字节。
2. 将本任务目录映射为一个空闲的ASCII短盘符（例如`subst Z: "完整任务路径"`）。原机器Z:已用于本轮目录，复现者应选择自己的空闲盘符。
3. 使用Python 3.11以上执行：`python Z:/scripts/replay_xsim.py --vivado F:/Xilinx/Vivado/2022.2`。脚本要求版本2022.2，直接使用归档网表、SDF和激励，输出仅写新的`build/replay_xsim/`，已有目录会拒绝覆盖。

此脚本保留本轮实际编译参数、MAX外部注释、脉冲传输和完整timing check。它是复现入口，本轮结束时只进行语法和路径检查，没有为了测试入口重复执行完整仿真。原实际执行入口为`run_xsim.py`，真实命令、注释日志、run_manifest及原始输出均已归档。

## 原机脚本与路径映射

阶段脚本保留原执行路径，不能直接在其他机器无检查地重跑。原工作盘符为Z:本任务、W:05核心时序优化、Y:04合并、X:03辅助检测、U:01时序优化。历史目录在同一Git分支的`codex_generate/`下；W:/github是05原归档克隆，不能改指为06分支后运行冻结检查。其余工程、工具安装路径见各脚本常量。

只读导出入口为`export_sdf.tcl`，唯一来源是05的`results/compensated/design.dcp`，哈希见`inputs/SOURCE_MANIFEST.json`。不需要重新综合、布局布线或生成DCP。纯数据分析入口是`analyze_results.py`、`analyze_timing.py`、`compare_versions.py`；它们会写结果，复现时先复制目录并调整ROOT，禁止对原验收目录重跑。历史对比需按上述映射提供历史结果，不能把缺失的04 SDF补造出来。

## 压缩证据

`inputs/LOG_COMPRESSION_MANIFEST.json`逐项列出原始大小、原始SHA256、gzip路径和压缩大小。Git使用无损gzip保存大型日志及`TIMING_VIOLATIONS.csv`，本地原件均保留。用Python `gzip.open`解压到新文件后，SHA256应等于清单中的`uncompressed_sha256`；CSV编码及换行均保持原样。原始EDGE/PULSE和各级采样CSV直接保存，没有筛除异常样本。

`FILE_LIST.md`列出实际上传文件，`ARCHIVE_SELECTION.json`说明工具缓存、重复包装输出等未提交项。原厂仿真库、Vivado安装文件、商业手册和许可证不归档，由复现机器的合法2022.2安装提供。未重复上传旧DCP、RTL或BIT；05源版本已在父提交中完整保存，本轮未生成BIT。

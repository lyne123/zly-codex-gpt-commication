# 2026-11-07-03 辅助跨帧匹配时序优化

最终数字验收和核心时序通过，采用一拍专用确认流水及粗计数采样对齐。Corrected BIT/LTX 位于 `implementation/`，**本任务没有烧录板卡**。完整结论见 [RESULTS.md](RESULTS.md)，机器可读验收见 [VALIDATION.json](VALIDATION.json)。

- [时序对照](TIMING_BEFORE_AFTER.md)：核心 Setup/Hold +0.099/+0.054 ns；14 条历史 ILA2 负端点保留。
- [功能等价与延迟说明](DESIGN_EQUIVALENCE.md)：F 功能规则不变，输出整组增加 1 拍，Locate 保持五级。
- [复现步骤](REPRODUCE.md)、[上板 A/B 方法](HARDWARE_AB_TEST.md)。
- `production_original/rtl/`：完整原生产 RTL；`reference_F/rtl/`：完整 F；`variants/I_confirmation_pipe/`：完整最终 RTL。
- `RTL.diff`、`PRODUCTION_RTL.diff`：分别相对 F 和原生产版。
- `inputs/`：真实 ILA CSV、冻结参数、XCI、XDC、原始 3512 脉冲与真实时间参考。
- `results/I_confirmation_pipe/`：组合检查、真实重放、三组 RTL 与错误/回卷检查；`results/sdf/`：两版原始逐事件 CSV、完整压缩日志和注释证据。
- `results/PRECISION_COMPARISON.csv`：各组及共同事件精度；`results/timing/`：成功和失败的原始报告。
- `implementation/`：最终路由/综合 DCP、MAX SDF、网表、BIT/LTX 及有效约束；大文件使用 Git LFS。
- `SHA256SUMS.txt` 和 `FILE_LIST.csv`：校验与文件清单，均不包含自身以避免循环。

未重复上传中间失败 DCP、原生产 BIT、旧 Debug BIT、原生产 DCP、Vivado 缓存及重复输出。历史输入仍在原任务；本地中间实现路径、大小、SHA256 见 `results/LOCAL_INTERMEDIATE_FILES.json`。必要最终实现和所有本轮原始 CSV/失败日志均归档。完整 SDF 日志无损压缩，原日志位置和校验值见各 `RUN_MANIFEST.json`。没有因文件过大遗漏验收证据。

`inputs/SOURCE.json` 是开始状态冻结，不代表最终状态；最终新增流水延迟和正式修改以 `VALIDATION.json` 为准。本地另有同编号 ATC 任务目录，原样保留；本任务按用户明确给定名称创建，未覆盖它。GitHub 只归档本任务及追加索引，不合并 main，不强推。

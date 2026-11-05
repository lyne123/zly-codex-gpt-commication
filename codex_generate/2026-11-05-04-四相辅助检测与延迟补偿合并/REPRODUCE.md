# 复现与当前停止门槛

所有运行应在新的工作副本中，禁止覆盖此处冻结CSV、日志和实现文件。正式Baseline不修改。
Windows短路径映射：W:=本任务副本；X:=2026-11-05-03辅助任务；U:=2026-11-05-01时序优化任务；V:=2026-11-05-02定位任务。
工具：F:/Program Files/Python313/python.exe；F:/iverilog/bin；F:/Xilinx/Vivado/2022.2/bin。Vivado的实际工作目录使用W:/logs，避免中文路径工具缺陷。

1. rtl/5个文件是已冻结合并结果，inputs/compensation_params.tcl及sim/compensation_parameters.vh保存原参数，勿重新运行校准脚本。
2. 在空结果目录运行scripts/run_rtl.py，得到全3512旁路/补偿数据及8321个Locate边界检查。
3. 运行prepare_build.py、Vivado register_ip.tcl、build_compensated.tcl，只导出路由结果不写BIT。
4. 只读运行audit_failure.tcl，再运行review_implementation.py（同时检查模块from/to输入边界）。
5. 当前核心STA失败，按任务约定到此停止。final_validation.py写FAIL并禁止BIT；finalize_stopped.py生成当前停止报告。

scripts/prepare_gate.py、run_gate.py、analyze_gate.py、compare_results.py保留后续验证入口，但本次未执行其SDF动作，不能视为已经验证过的新SDF观察映射。run_gate.py full要求main_static_pass=true。
未来修复应作为新的独立任务保存新实现，不覆盖此次失败证据；通过STA后再prepare/compile/full，完整仿真保持时序检查启用。full stimulus和truth均来自6b341d8，SHA已冻结。
final_validation.py只有RTL、核心STA、完整SDF、原参数算术/残余偏差及数据格式全部通过，才调用单独BIT脚本。当前不会调用。

本任务只有RTL功能仿真和实际综合实现/只读STA审查已经运行。MATLAB/硬件/新补偿校准均未执行。

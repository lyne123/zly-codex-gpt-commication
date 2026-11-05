#
#Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
#
set_param logicopt.enablePowerLopt 0
set_param project.singleFileAddWarning.threshold 0
set_param chipscope.maxJobs 1
set_param logicopt.controlSetOpt 1
set_param logicopt.enableAutoBUFGtoMBUFGXform 1
set_param synth.enableIncremental 0
set_param chipscope.flow 0
set part xc7k325tffg900-2
set board_part_repo_paths {}
set board_part {}
set board_connections {}
set tool_flow Vivado
set ip_vlnv xilinx.com:ip:xsdbm:3.0
set ip_module_name dbg_hub
set params {{{PARAM_VALUE.C_BSCAN_MODE} {false} {PARAM_VALUE.C_BSCAN_MODE_WITH_CORE} {false} {PARAM_VALUE.C_CLK_INPUT_FREQ_HZ} {300000000} {PARAM_VALUE.C_ENABLE_CLK_DIVIDER} {false} {PARAM_VALUE.C_EN_BSCANID_VEC} {false} {PARAM_VALUE.C_NUM_BSCAN_MASTER_PORTS} {0} {PARAM_VALUE.C_TWO_PRIM_MODE} {false} {PARAM_VALUE.C_USER_SCAN_CHAIN} {1} {PARAM_VALUE.C_USE_EXT_BSCAN} {false} {PARAM_VALUE.C_XSDB_NUM_SLAVES} {2}}}
set intf_params {}
set connectivity {}
set output_xci U:/build/dbgpre/dbg_hub_CV.0/out/result.xci
set output_dcp U:/build/dbgpre/dbg_hub_CV.0/out/result.dcp
set output_dir U:/build/dbgpre/dbg_hub_CV.0/out
set ip_repo_paths {}
set ip_output_repo U:/build/shared_ip_cache
set ip_cache_permissions {read write}

set oopbus_ip_repo_paths [get_param chipscope.oopbus_ip_repo_paths]

set synth_opts {}
set xdc_files {}

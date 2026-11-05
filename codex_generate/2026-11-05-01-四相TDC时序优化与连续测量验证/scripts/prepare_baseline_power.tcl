# 复用已成功的同版综合，独立执行布局前BRAM模式恢复及定点寄存器复制试验。
set_param general.maxThreads 2
open_project U:/build/baseline/timing_baseline.xpr
config_ip_cache -use_cache_location U:/build/shared_ip_cache
foreach script {restore_bram_mode.tcl replicate_ila_drivers.tcl} {
    add_files -fileset utils_1 -norecurse U:/scripts/$script
}
reset_run impl_1
set_property STEPS.OPT_DESIGN.TCL.POST U:/scripts/restore_bram_mode.tcl [get_runs impl_1]
set_property STEPS.PHYS_OPT_DESIGN.TCL.POST U:/scripts/replicate_ila_drivers.tcl [get_runs impl_1]
set_property STEPS.PLACE_DESIGN.ARGS.DIRECTIVE ExtraPostPlacementOpt [get_runs impl_1]
launch_runs impl_1 -to_step route_design -scripts_only -dir U:/build/rbaseline_power -jobs 1
puts "RUN_DIRECTORY=[get_property DIRECTORY [get_runs impl_1]]"
close_project

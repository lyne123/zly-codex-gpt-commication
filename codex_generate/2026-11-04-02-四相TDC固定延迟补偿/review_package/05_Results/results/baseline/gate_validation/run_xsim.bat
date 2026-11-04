@echo off
call "F:\Xilinx\Vivado\2022.2\bin\xsim.bat" tb_tdc_time_impl -tclbatch run_all.tcl -log baseline_validation.log -testplusarg "STIMULUS=T:/sim/stimuli/validation.txt" -testplusarg "OUTPUT_DIR=T:/results/baseline/gate_validation"
exit /b %errorlevel%

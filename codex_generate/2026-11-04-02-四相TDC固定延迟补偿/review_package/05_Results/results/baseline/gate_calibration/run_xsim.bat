@echo off
call "F:\Xilinx\Vivado\2022.2\bin\xsim.bat" tb_tdc_time_impl -tclbatch run_all.tcl -log baseline_calibration.log -testplusarg "STIMULUS=T:/sim/stimuli/calibration.txt" -testplusarg "OUTPUT_DIR=T:/results/baseline/gate_calibration"
exit /b %errorlevel%

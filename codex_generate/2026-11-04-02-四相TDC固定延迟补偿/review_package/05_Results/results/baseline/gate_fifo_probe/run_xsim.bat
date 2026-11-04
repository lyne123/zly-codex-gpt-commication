@echo off
call "F:\Xilinx\Vivado\2022.2\bin\xsim.bat" tb_tdc_time_impl -tclbatch run_all.tcl -log baseline_fifo_probe.log -testplusarg "STIMULUS=T:/sim/stimuli/fifo_probe.txt" -testplusarg "OUTPUT_DIR=T:/results/baseline/gate_fifo_probe"
exit /b %errorlevel%

@echo off
call "F:/Xilinx/Vivado/2022.2/bin/xsim.bat" measurement -tclbatch run_all.tcl -log "U:/results/optimized/baseline/gate_calibration/simulation.log" -testplusarg "STIMULUS=U:/results/optimized/baseline/gate_calibration/stimulus.txt" -testplusarg "OUTPUT_DIR=U:/results/optimized/baseline/gate_calibration"
exit /b %errorlevel%

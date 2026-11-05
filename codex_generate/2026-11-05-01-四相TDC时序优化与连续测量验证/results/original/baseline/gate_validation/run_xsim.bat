@echo off
call "F:/Xilinx/Vivado/2022.2/bin/xsim.bat" measurement -tclbatch run_all.tcl -log "U:/results/original/baseline/gate_validation/simulation.log" -testplusarg "STIMULUS=U:/results/original/baseline/gate_validation/stimulus.txt" -testplusarg "OUTPUT_DIR=U:/results/original/baseline/gate_validation"
exit /b %errorlevel%

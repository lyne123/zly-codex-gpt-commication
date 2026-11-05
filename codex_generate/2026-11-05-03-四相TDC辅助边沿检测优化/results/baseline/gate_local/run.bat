@echo off
call "F:/Xilinx/Vivado/2022.2/bin/xsim.bat" measurement -tclbatch run_all.tcl -log "W:/results/baseline/gate_local/simulation.log" -testplusarg "STIMULUS=W:/results/baseline/gate_local/stimulus.txt" -testplusarg "OUTPUT_DIR=W:/results/baseline/gate_local" -testplusarg "TIME_SHIFT=225280000"
exit /b %errorlevel%

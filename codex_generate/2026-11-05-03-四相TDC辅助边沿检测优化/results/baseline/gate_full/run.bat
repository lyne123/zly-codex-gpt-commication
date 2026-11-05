@echo off
call "F:/Xilinx/Vivado/2022.2/bin/xsim.bat" measurement -tclbatch run_all.tcl -log "W:/results/baseline/gate_full/simulation.log" -testplusarg "STIMULUS=W:/results/baseline/gate_full/stimulus.txt" -testplusarg "OUTPUT_DIR=W:/results/baseline/gate_full" -testplusarg "TIME_SHIFT=0"
exit /b %errorlevel%

@echo off
call "F:/Xilinx/Vivado/2022.2/bin/xsim.bat" measurement -tclbatch run_all.tcl -log "Z:/logs/simulation.log" -testplusarg "STIMULUS=Z:/results/compensated/gate_full/stimulus.txt" -testplusarg "OUTPUT_DIR=Z:/results/compensated/gate_full" -testplusarg "TIME_SHIFT=0"
exit /b %errorlevel%

@echo off
call "F:\Xilinx\Vivado\2022.2\bin/xvlog.bat" --incr --relax -L uvm -prj compile.prj -log xvlog.log
if errorlevel 1 exit /b 1
call "F:\Xilinx\Vivado\2022.2\bin/xelab.bat" --incr --O3 --debug off --relax --mt 2 --maxdelay -d "GATE_NETLIST=" -L xil_defaultlib -L uvm -L simprims_ver -L secureip --snapshot measurement -transport_int_delays -pulse_r 0 -pulse_int_r 0 -pulse_e 0 -pulse_int_e 0 xil_defaultlib.tb_tdc xil_defaultlib.glbl -log elaborate.log
exit /b %errorlevel%

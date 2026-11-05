`timescale 1ps/1ps
// 所有监测均为测试平台逻辑，不进入正式网表。
module tb_tdc;
    reg sys_clk=0, sys_rst_n=0, pwm_in=0;
    always #5000 sys_clk=~sys_clk;
`ifdef COMPENSATED_RTL
    `include "compensation_parameters.vh"
    tdc_meas_top `COMPENSATION_PARAMETERS dut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
`else
    tdc_meas_top dut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
`endif
`ifdef GATE_NETLIST
    wire monitor_rst_500=dut.rst_sync_500m[1];
    wire monitor_rst_100=dut.rst_sync_100m[1];
`ifdef OPTIMIZED_GATE_NETLIST
    // 新综合策略导出的总线名不同，仅适配测试平台观察点。
    wire [9:0] monitor_coarse=dut.u_tdc_time_locate.coarse_counter;
`else
    wire [9:0] monitor_coarse=dut.u_tdc_time_locate.coarse_counter_reg;
`endif
    // repeat_error在综合网表中因未连接而删除，只能由已输出候选重建同极性重复。
    reg previous_emitted_valid=0,previous_emitted_type=0;
    wire monitor_repeat=previous_emitted_valid && dut.edge_valid &&
                        (previous_emitted_type==dut.edge_type_q);
`else
    wire monitor_rst_500=dut.rst_n_500m;
    wire monitor_rst_100=dut.rst_n_100m;
    wire [9:0] monitor_coarse=dut.u_tdc_time_locate.coarse_counter;
    wire monitor_repeat=dut.repeat_error;
`endif
`ifdef AUX_MODE
    defparam dut.u_tdc_fine_layer.ENABLE_AUX_4PHASE=`AUX_MODE;
`endif
`ifndef GATE_NETLIST
    // 仅测试平台注入辅助输入路径延迟，顶层真实输入及真值文件不变。
    integer aux_input_delay=0;
    reg delayed_aux=0;
    // 延迟非阻塞赋值保留每条输入转换，避免惯性延迟错误过滤短脉冲。
    always @(pwm_in) delayed_aux <= #(aux_input_delay) pwm_in;
    initial begin
        if ($value$plusargs("AUX_INPUT_DELAY_PS=%d",aux_input_delay)) begin end
        force dut.u_tdc_fine_layer.pwm_aux_in=delayed_aux;
    end
    integer input_rises=0,input_falls=0,transport_rises=0,transport_falls=0;
    integer tdl_rises=0,tdl_falls=0,path_fd;
    // 输入从10us以后开始，计数从5us开始排除模型上电X→0初始化。
    always @(posedge pwm_in) if($time>5000000) input_rises=input_rises+1;
    always @(negedge pwm_in) if($time>5000000) input_falls=input_falls+1;
    always @(posedge delayed_aux) if($time>5000000) transport_rises=transport_rises+1;
    always @(negedge delayed_aux) if($time>5000000) transport_falls=transport_falls+1;
    always @(posedge dut.u_tdc_fine_layer.pwm_tdl[0]) if($time>5000000) tdl_rises=tdl_rises+1;
    always @(negedge dut.u_tdc_fine_layer.pwm_tdl[0]) if($time>5000000) tdl_falls=tdl_falls+1;
`endif
    string stimulus, output_dir, sdf_file;
    integer src, rc, id, raw_fd, cand_fd, ts_fd, width_fd, err_fd, fifo_fd, epoch_fd, taps_fd, error_fifo_fd, trace_fd;
    time rise_ps, fall_ps, period_ps;
    reg epoch_written=0;
    initial begin
        if (!$value$plusargs("STIMULUS=%s",stimulus)) $fatal(1,"Missing STIMULUS");
        if (!$value$plusargs("OUTPUT_DIR=%s",output_dir)) $fatal(1,"Missing OUTPUT_DIR");
        raw_fd=$fopen({output_dir,"/raw.csv"},"w");
        cand_fd=$fopen({output_dir,"/candidate.csv"},"w");
        ts_fd=$fopen({output_dir,"/timestamps.csv"},"w");
        width_fd=$fopen({output_dir,"/widths.csv"},"w");
        err_fd=$fopen({output_dir,"/errors.csv"},"w");
        fifo_fd=$fopen({output_dir,"/fifo.csv"},"w");
        epoch_fd=$fopen({output_dir,"/clock_epoch.csv"},"w");
        taps_fd=$fopen({output_dir,"/sampled_taps.csv"},"w");
        error_fifo_fd=$fopen({output_dir,"/error_fifo.csv"},"w");
        trace_fd=$fopen({output_dir,"/anomaly_pipeline_trace.csv"},"w");
        if (!raw_fd || !cand_fd || !ts_fd || !width_fd || !err_fd || !fifo_fd || !epoch_fd || !taps_fd || !error_fifo_fd)
            $fatal(1,"Cannot open output files");
        $fdisplay(raw_fd,"time_ps,coarse,mask,polarity,codes");
        $fdisplay(cand_fd,"time_ps,coarse,type,index,code,conflict,repeat_error");
        $fdisplay(ts_fd,"time_ps,type,timestamp_ps");
        $fdisplay(width_fd,"time_ps,width_ps");
        $fdisplay(err_fd,"time_ps,kind,code");
        $fdisplay(fifo_fd,"time_ps,width_ps");
        $fdisplay(epoch_fd,"epoch_ps");
        $fdisplay(taps_fd,"time_ps,phase,thermo_hex,carry_hex");
        $fdisplay(error_fifo_fd,"time_ps,code");
        $fdisplay(trace_fd,"time_ps,sync_valid,mask,polarity,codes,edge_valid,edge_type,index,code,conflict,repeat_error,timestamp_valid,timestamp_type,timestamp_ps,width_valid,width_ps,result_wr_en,error_wr_en,error_valid,error_code,result_full,error_full,result_overflow,error_overflow");
`ifdef GATE_SDF
        if (!$value$plusargs("SDF=%s",sdf_file)) $fatal(1,"Missing SDF");
        $sdf_annotate(sdf_file,dut,,"sdf_annotation.log","MAXIMUM");
`endif
        #200000 sys_rst_n=1;
        src=$fopen(stimulus,"r");
        if (!src) $fatal(1,"Cannot open stimulus");
        while (!$feof(src)) begin
            rc=$fscanf(src,"%d %d %d %d\n",id,rise_ps,fall_ps,period_ps);
            if (rc==4) begin
                if (rise_ps<$time || fall_ps<=rise_ps) $fatal(1,"Invalid stimulus");
                #(rise_ps-$time) pwm_in=1;
                #(fall_ps-$time) pwm_in=0;
            end else if (!$feof(src)) $fatal(1,"Malformed stimulus");
        end
        $fclose(src);
        #500000;
`ifndef GATE_NETLIST
        path_fd=$fopen({output_dir,"/PATH_EDGE_COUNTS.csv"},"w");
        $fdisplay(path_fd,"input_rises,input_falls,aux_path_rises,aux_path_falls,tdl0_path_rises,tdl0_path_falls");
        $fdisplay(path_fd,"%0d,%0d,%0d,%0d,%0d,%0d",input_rises,input_falls,transport_rises,transport_falls,tdl_rises,tdl_falls);
        $fclose(path_fd);
        if(input_rises!=transport_rises || input_falls!=transport_falls || input_rises!=tdl_rises || input_falls!=tdl_falls)
            $fatal(1,"测试平台路径模型丢失了输入转换");
`endif
        $display("TDC_SIM_DONE time_ps=%0t",$time);
        $fclose(raw_fd); $fclose(cand_fd); $fclose(ts_fd); $fclose(width_fd);
        $fclose(err_fd); $fclose(fifo_fd); $fclose(epoch_fd);
        $fclose(taps_fd);
        $fclose(error_fifo_fd);
        $fclose(trace_fd);
        $finish;
    end
    task record_taps;
        input integer phase;
        input [63:0] thermo,carry_bits;
        begin
            // 全0/全1为无细测信息的稳定电平；X和非均匀采样必须保留。
            if ($time>=10000000 && taps_fd && thermo!==64'd0 && thermo!==64'hffffffffffffffff) begin
                $fdisplay(taps_fd,"%0t,%0d,%016h,%016h",$time,phase,thermo,carry_bits);
                if (^thermo===1'bx) $fdisplay(err_fd,"%0t,tap_unknown_%0d,1",$time,phase);
            end
        end
    endtask
    always @(negedge dut.clk_500m)
        record_taps(0,dut.u_tdc_fine_layer.u_tdl0.thermo_q,dut.u_tdc_fine_layer.u_tdl0.carry_tap);
    always @(negedge dut.clk_500m_deg90)
        record_taps(90,dut.u_tdc_fine_layer.u_tdl90.thermo_q,dut.u_tdc_fine_layer.u_tdl90.carry_tap);
    always @(negedge dut.clk_500m_deg180)
        record_taps(180,dut.u_tdc_fine_layer.u_tdl180.thermo_q,dut.u_tdc_fine_layer.u_tdl180.carry_tap);
    always @(negedge dut.clk_500m_deg270)
        record_taps(270,dut.u_tdc_fine_layer.u_tdl270.thermo_q,dut.u_tdc_fine_layer.u_tdl270.carry_tap);

    // 在半周期后读取已稳定的数据；网表中实际保留的信号名需单独核对。
    always @(negedge dut.clk_500m) begin
        if (monitor_rst_500 && raw_fd) begin
            // 覆盖原异常前后的每一级接口，包括没有valid的周期；不改变主激励。
            if (($time>=238600000 && $time<=238900000) ||
                ($time>=241900000 && $time<=242200000) ||
                ($time>=245200000 && $time<=245500000))
                $fdisplay(trace_fd,"%0t,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",$time,
                    dut.sync_valid,dut.sync_edge_valid,dut.sync_edge_polarity,dut.all_fine_code,
                    dut.edge_valid,dut.edge_type_q,dut.sel_index,dut.chosen_code,dut.polarity_conflict,monitor_repeat,
                    dut.timestamp_valid,dut.timestamp_edge_type,dut.timestamp_ps,dut.pulse_width_valid,dut.pulse_width_ps,
                    dut.result_fifo_wr_en,dut.error_fifo_wr_en,dut.error_event_valid,dut.error_event_code,
                    dut.result_fifo_full,dut.error_fifo_full,dut.result_fifo_overflow,dut.error_fifo_overflow);
            if (!epoch_written && (^monitor_coarse !== 1'bx)) begin
                $fdisplay(epoch_fd,"%0d",$time-monitor_coarse*2000+1000);
                epoch_written=1;
            end
            if (dut.sync_valid && (|dut.sync_edge_valid))
                $fdisplay(raw_fd,"%0t,%0d,%0d,%0d,%0d",$time,
                    monitor_coarse,dut.sync_edge_valid,
                    dut.sync_edge_polarity,dut.all_fine_code);
            if (dut.edge_valid)
                $fdisplay(cand_fd,"%0t,%0d,%0d,%0d,%0d,%0d,%0d",$time,
                    monitor_coarse,dut.edge_type_q,
                    dut.sel_index,dut.chosen_code,dut.polarity_conflict,monitor_repeat);
            if (dut.timestamp_valid)
                $fdisplay(ts_fd,"%0t,%0d,%0d",$time,dut.timestamp_edge_type,dut.timestamp_ps);
            if (dut.pulse_width_valid)
                $fdisplay(width_fd,"%0t,%0d",$time,dut.pulse_width_ps);
            if (dut.error_event_valid)
                $fdisplay(err_fd,"%0t,merge,%0d",$time,dut.error_event_code);
            if (dut.polarity_conflict) $fdisplay(err_fd,"%0t,conflict,1",$time);
            if (monitor_repeat) $fdisplay(err_fd,"%0t,repeat,1",$time);
            if (dut.result_fifo_overflow || dut.error_fifo_overflow)
                $fdisplay(err_fd,"%0t,overflow,1",$time);
            if ($time>5000000 && (^{dut.sync_valid,dut.sync_edge_valid,dut.edge_valid,
                dut.timestamp_valid,dut.pulse_width_valid,dut.result_fifo_overflow,
                dut.error_fifo_overflow} === 1'bx))
                $fdisplay(err_fd,"%0t,unknown_control,1",$time);
            if (dut.timestamp_valid && (^dut.timestamp_ps === 1'bx))
                $fdisplay(err_fd,"%0t,unknown_timestamp,1",$time);
            if (dut.pulse_width_valid && (^dut.pulse_width_ps === 1'bx))
                $fdisplay(err_fd,"%0t,unknown_width,1",$time);
`ifdef GATE_NETLIST
            if (dut.edge_valid) begin
                previous_emitted_valid=1;
                previous_emitted_type=dut.edge_type_q;
            end
`endif
        end
    end
    always @(negedge dut.clk_100m) begin
        if (monitor_rst_100 && fifo_fd && dut.pulse_width_valid_100m)
            $fdisplay(fifo_fd,"%0t,%0d",$time,dut.pulse_width_ps_100m);
        if (monitor_rst_100 && error_fifo_fd && dut.error_valid_100m)
            $fdisplay(error_fifo_fd,"%0t,%0d",$time,dut.error_code_100m);
    end
    initial begin
        #1000000000;
        $fatal(1,"Simulation watchdog timeout");
    end
`ifdef AUX_MODE
`include "aux_monitor.svh"
`endif
// 只读检查复位末级副本与原同步器同拍，写门控的所有条件保持原逻辑。
always @(dut.rst_result_fifo_500m or dut.rst_n_500m) begin
    #1;
    if(dut.rst_result_fifo_500m!==dut.rst_n_500m) $fatal(1,"结果FIFO复位副本与原末级不等价");
end
endmodule

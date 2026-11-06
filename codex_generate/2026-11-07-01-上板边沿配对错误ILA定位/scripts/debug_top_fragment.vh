// 以下逻辑仅属于独立Debug副本；任何输出均不回馈测量、复位或FIFO通路。
wire debug_trigger_a = error_event_valid && (error_event_code == 4'd1);
wire debug_trigger_b = error_event_valid && (error_event_code == 4'd2);
reg [31:0] debug_double_rise_count, debug_orphan_fall_count;
reg [31:0] debug_cycle;
reg debug_last_edge_type, debug_have_last_edge, debug_last_rise_paired;
always @(posedge clk_500m or negedge rst_n_500m) begin
    if (!rst_n_500m) begin
        debug_double_rise_count <= 0;
        debug_orphan_fall_count <= 0;
        debug_cycle <= 0;
        debug_last_edge_type <= 0;
        debug_have_last_edge <= 0;
        debug_last_rise_paired <= 0;
    end else begin
        debug_cycle <= debug_cycle + 1'b1;
        if (debug_trigger_a) debug_double_rise_count <= debug_double_rise_count + 1'b1;
        if (debug_trigger_b) debug_orphan_fall_count <= debug_orphan_fall_count + 1'b1;
        if (timestamp_valid && debug_in_range) begin
            debug_last_edge_type <= timestamp_edge_type;
            debug_have_last_edge <= 1;
            if (timestamp_edge_type) debug_last_rise_paired <= 0;
            else if (debug_rise_pending) debug_last_rise_paired <= 1;
        end
    end
end

// 每个源信号只增加影子寄存器负载。全部探针统一延迟一拍；ILA另有四拍输入流水。
// 这些延迟只作用于观测数据，不改变任何正式valid或数据的时序。
(* DONT_TOUCH="TRUE", SHREG_EXTRACT="NO" *) reg [31:0] debug_control_q;
(* DONT_TOUCH="TRUE", SHREG_EXTRACT="NO" *) reg [39:0] debug_raw_q;
(* DONT_TOUCH="TRUE", SHREG_EXTRACT="NO" *) reg [63:0] debug_aux_q;
(* DONT_TOUCH="TRUE", SHREG_EXTRACT="NO" *) reg [39:0] debug_pipeline_q;
(* DONT_TOUCH="TRUE", SHREG_EXTRACT="NO" *) reg [20:0] debug_timestamp_q, debug_rise_ts_q;
(* DONT_TOUCH="TRUE", SHREG_EXTRACT="NO" *) reg [63:0] debug_counts_q;
(* DONT_TOUCH="TRUE", SHREG_EXTRACT="NO" *) reg [31:0] debug_cycle_q;
always @(posedge clk_500m) begin
    debug_control_q <= {8'd0, debug_frame_ready, sync_valid, mmcm_locked, rst_n_500m,
        error_fifo_overflow, result_fifo_overflow, pulse_width_valid,
        repeat_error, polarity_conflict, edge_valid, timestamp_edge_type, timestamp_valid,
        debug_last_rise_paired, debug_have_last_edge, debug_last_edge_type,
        debug_in_range, debug_rise_pending, error_event_code, error_event_valid,
        debug_trigger_b, debug_trigger_a};
    debug_raw_q <= debug_raw_packets;
    debug_aux_q <= debug_aux;
    debug_pipeline_q <= {2'd0, debug_frame_ready, debug_final_types,
        timestamp_edge_type, timestamp_valid, repeat_error, polarity_conflict,
        edge_type_q, edge_valid, chosen_code, sel_index, sync_valid,
        sync_edge_polarity, sync_edge_valid};
    debug_timestamp_q <= timestamp_ps;
    debug_rise_ts_q <= debug_rise_timestamp;
    debug_counts_q <= {debug_orphan_fall_count,debug_double_rise_count};
    debug_cycle_q <= debug_cycle;
end

ila_edge_debug u_ila_edge_debug (
    .clk(clk_500m), .probe0(debug_control_q), .probe1(debug_raw_q),
    .probe2(debug_aux_q), .probe3(debug_pipeline_q), .probe4(debug_timestamp_q),
    .probe5(debug_rise_ts_q), .probe6(debug_counts_q), .probe7(debug_cycle_q)
);

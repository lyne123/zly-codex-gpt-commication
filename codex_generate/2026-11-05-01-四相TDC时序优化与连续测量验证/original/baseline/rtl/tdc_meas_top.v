module tdc_meas_top #(
    parameter integer COARSE_W = 10,         // 500 MHz: 2048 ns wrap period
    parameter integer TAP_PS = 10,
    parameter integer CARRY_NUM = 16,          // 16个CARRY4
    parameter integer TAPS      = CARRY_NUM*4  // 64 taps
)(
    // input  wire             clk_500m,
    // input  wire             clk_500m_deg90,
    // input  wire             clk_500m_deg180,
    // input  wire             clk_500m_deg270,
    input  wire             sys_clk,
    input  wire             sys_rst_n,
    input  wire             pwm_in

    // output wire [7:0] sync_code0,
    // output wire [7:0] sync_code90,
    // output wire [7:0] sync_code180,
    // output wire [7:0] sync_code270
);
localparam integer TIME_W = COARSE_W + 11;

//============================================================
// 1. 时钟生成
//============================================================
wire clk_500m, clk_500m_deg90, clk_500m_deg180, clk_500m_deg270, clk_100m;
wire mmcm_locked;

wire rst_async_n = sys_rst_n & mmcm_locked;

// Asynchronous assertion, synchronized release in each local clock domain.
(* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg [1:0] rst_sync_500m;
(* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg [1:0] rst_sync_100m;
always @(posedge clk_500m or negedge rst_async_n) begin
    if (!rst_async_n) rst_sync_500m <= 2'b00;
    else              rst_sync_500m <= {rst_sync_500m[0], 1'b1};
end
always @(posedge clk_100m or negedge rst_async_n) begin
    if (!rst_async_n) rst_sync_100m <= 2'b00;
    else              rst_sync_100m <= {rst_sync_100m[0], 1'b1};
end
wire rst_n_500m = rst_sync_500m[1];
wire rst_n_100m = rst_sync_100m[1];

clk_wiz_0 u_clk_wiz_0 (
    // Clock out ports
    .clk_out1(clk_500m),     // output clk_out1
    .clk_out2(clk_500m_deg90),     // output clk_out2
    .clk_out3(clk_500m_deg180),     // output clk_out3
    .clk_out4(clk_500m_deg270),     // output clk_out4
    .clk_out5(clk_100m),     // output clk_out5
   // Status and control signals
    .reset(~sys_rst_n), // input reset
    .locked(mmcm_locked),       // output locked
   // Clock in ports
    .clk_in1(sys_clk)      // input clk_in1
);

//============================================================
// 2. 四路TDL分别采样。
//============================================================
(* DONT_TOUCH = "TRUE" *)
wire [31:0] all_fine_code;
wire sync_valid;
wire [3:0] sync_edge_valid;
wire [7:0] sync_edge_polarity;

(* DONT_TOUCH = "TRUE" *)
tdc_fine_layer #(
    .CARRY_NUM(CARRY_NUM)
) u_tdc_fine_layer (
    .clk_500m(clk_500m),
    .clk_500m_deg90(clk_500m_deg90),
    .clk_500m_deg180(clk_500m_deg180),
    .clk_500m_deg270(clk_500m_deg270),
    .rst_n(rst_async_n),
    .pwm_in(pwm_in),

    .all_fine_code(all_fine_code),
    .sync_valid(sync_valid),
    .sync_edge_valid(sync_edge_valid),
    .sync_edge_polarity(sync_edge_polarity)
);

// ila_0 u_ila (
//     .clk    (clk_100m),
//     .probe0 (all_fine_code[7:0]),
//     .probe1 (all_fine_code[15:8]),
//     .probe2 (all_fine_code[23:16]),
//     .probe3 (all_fine_code[31:24]),
//     .probe4 (sync_valid),
//     .probe5 (sync_edge_valid),
//     .probe6 (sync_edge_polarity)
// );
    //============================================================
    // 3. 候选选择、相对粗中细定位、时间戳与脉宽计算
    //============================================================
    wire edge_valid;
    wire edge_type_q;
    wire [7:0] chosen_code;
    wire [1:0] sel_index;
    wire repeat_error, polarity_conflict;

    tdc_time_candicate u_tdc_time_candicate (
        .clk_500m             (clk_500m),
        .rst_n                (rst_n_500m),
        .sync_valid           (sync_valid),
        .all_fine_code        (all_fine_code),
        .sync_edge_valid      (sync_edge_valid),
        .sync_edge_polarity   (sync_edge_polarity),
        // 1
        .edge_valid           (edge_valid),
        .edge_type_q          (edge_type_q),
        .chosen_code          (chosen_code),
        .sel_index            (sel_index),
        .polarity_conflict    (polarity_conflict),
        .repeat_error         (repeat_error)
    );

    // ila_1 u_ila1 (
    //     .clk    (clk_100m),
    //     .probe0 ({edge_valid,edge_type_q}),
    //     .probe1 (chosen_code),
    //     .probe2 (sel_index),
    //     .probe3 ({polarity_conflict,repeat_error})
    // );
//============================================================
// 4. 单边沿时间戳合并
//============================================================
    wire located_valid, located_edge_type;
    wire [COARSE_W-1:0] coarse_value;
    wire [1:0] mid_value;
    wire [7:0] fine_tap_count;
    wire [5:0] fine_10ps;
    wire timestamp_valid, timestamp_edge_type;
    wire [COARSE_W+10:0] timestamp_ps;


    tdc_time_locate #(
        .COARSE_W (COARSE_W),
        .MAX_TAP  (TAPS),
        .TAP_PS   (TAP_PS)
    ) u_tdc_time_locate (
        .clk_500m             (clk_500m),
        .rst_n                (rst_n_500m),
        .edge_valid           (edge_valid),
        .edge_type_q          (edge_type_q),
        .chosen_code          (chosen_code),
        .sel_index            (sel_index),
        .polarity_conflict    (polarity_conflict),
        .repeat_error         (repeat_error),

        .timestamp_valid      (timestamp_valid),
        .timestamp_edge_type  (timestamp_edge_type),
        .timestamp_ps       (timestamp_ps)
    );

    ila_2 u_ila2 (
    .clk    (clk_500m),
    .probe0 ({timestamp_valid,(timestamp_edge_type?1'b1:1'b0)}),
    .probe1 (timestamp_ps)
);

//============================================================
// 5. 脉宽合并
//============================================================
wire pulse_width_valid;
wire [COARSE_W+10:0] pulse_width_ps;
wire error_event_valid;
wire [3:0] error_event_code;

tdc_time_merge #(
    .COARSE_W (COARSE_W),
    .MAX_TAP  (TAPS),
    .TAP_PS   (TAP_PS)
) u_tdc_time_merge (
    .clk_500m             (clk_500m),
    .rst_n                (rst_n_500m),
    .timestamp_valid      (timestamp_valid),
    .timestamp_edge_type  (timestamp_edge_type),
    .timestamp_ps       (timestamp_ps),
    .pulse_width_valid    (pulse_width_valid),
    .pulse_width_ps       (pulse_width_ps),
    .error_valid          (error_event_valid),
    .error_code           (error_event_code)
);
//============================================================
// 6. 测量结果跨时钟域：500 MHz 写入，100 MHz 连续读出
// FIFO 配置：23 bit x 1024，Independent Clocks，Standard FIFO。
// 脉宽 FIFO 只保存有效脉宽；错误事件使用独立 FIFO，避免错配。
//============================================================
wire [22:0] result_fifo_dout;
wire result_fifo_full, result_fifo_empty;
wire result_fifo_wr_rst_busy, result_fifo_rd_rst_busy;
wire result_fifo_valid;

wire result_fifo_wr_en = rst_n_500m && !result_fifo_wr_rst_busy &&
                         !result_fifo_full && pulse_width_valid;
wire result_fifo_rd_en = rst_n_100m && !result_fifo_rd_rst_busy &&
                         !result_fifo_empty;

fifo_tdc_result u_fifo_tdc_result (
    .rst         (~rst_n_500m),
    .wr_clk      (clk_500m),
    .rd_clk      (clk_100m),
    .din         ({{(23-TIME_W){1'b0}}, pulse_width_ps}),
    .wr_en       (result_fifo_wr_en),
    .rd_en       (result_fifo_rd_en),
    .dout        (result_fifo_dout),
    .full        (result_fifo_full),
    .empty       (result_fifo_empty),
    .valid       (result_fifo_valid),
    .wr_rst_busy (result_fifo_wr_rst_busy),
    .rd_rst_busy (result_fifo_rd_rst_busy)
);

// Standard FIFO 的 valid 与 dout 对齐，不能使用 rd_en 代替。
wire pulse_width_valid_100m = rst_n_100m && !result_fifo_rd_rst_busy &&
                             result_fifo_valid;
wire [TIME_W-1:0] pulse_width_ps_100m = result_fifo_dout[TIME_W-1:0];



// 满或复位忙时无法接受结果；丢样状态保持到复位，供调试检查。
(* MARK_DEBUG = "TRUE" *) reg result_fifo_overflow;
always @(posedge clk_500m or negedge rst_n_500m) begin
    if (!rst_n_500m)
        result_fifo_overflow <= 1'b0;
    else if (pulse_width_valid && !result_fifo_wr_en)
        result_fifo_overflow <= 1'b1;
end

//============================================================
// 7. 错误事件跨时钟域：每次异常单独入队，避免与脉宽结果错配。
// FIFO 23-bit payload: [22:4]=0, [3:0]=error code (no timestamp).
//============================================================
wire [22:0] error_fifo_dout;
wire error_fifo_full, error_fifo_empty;
wire error_fifo_wr_rst_busy, error_fifo_rd_rst_busy;
wire error_fifo_valid;
wire error_fifo_wr_en = rst_n_500m && !error_fifo_wr_rst_busy &&
                        !error_fifo_full && error_event_valid;
wire error_fifo_rd_en = rst_n_100m && !error_fifo_rd_rst_busy &&
                        !error_fifo_empty;

fifo_tdc_result u_fifo_tdc_error (
    .rst         (~rst_n_500m),
    .wr_clk      (clk_500m),
    .rd_clk      (clk_100m),
    .din         ({19'd0, error_event_code}),
    .wr_en       (error_fifo_wr_en),
    .rd_en       (error_fifo_rd_en),
    .dout        (error_fifo_dout),
    .full        (error_fifo_full),
    .empty       (error_fifo_empty),
    .valid       (error_fifo_valid),
    .wr_rst_busy (error_fifo_wr_rst_busy),
    .rd_rst_busy (error_fifo_rd_rst_busy)
);

wire error_valid_100m = rst_n_100m &&
                                    !error_fifo_rd_rst_busy && error_fifo_valid;
wire [3:0] error_code_100m = error_fifo_dout[3:0];

ila_3 u_ila3 (
    .clk    (clk_100m),
    .probe0 (pulse_width_valid_100m),
    .probe1 (pulse_width_ps_100m),
    .probe2 (error_valid_100m),
    .probe3 (error_code_100m),
    .probe4 (pwm_in)
);

(* MARK_DEBUG = "TRUE" *) reg error_fifo_overflow;
always @(posedge clk_500m or negedge rst_n_500m) begin
    if (!rst_n_500m)
        error_fifo_overflow <= 1'b0;
    else if (error_event_valid && !error_fifo_wr_en)
        error_fifo_overflow <= 1'b1;
end

endmodule

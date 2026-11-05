`timescale 1ns/1ps

// 时间戳和脉宽统一使用 ps 为单位。
// timestamp_edge_type: 1=上升沿，0=下降沿。
// error_valid/error_code 为独立错误事件输出。

module tdc_time_merge #(
    parameter integer COARSE_W = 8,
    parameter integer MAX_TAP  = 64,
    parameter integer TAP_PS   = 10
)(
    input  wire                    clk_500m,
    input  wire                    rst_n,
    input  wire                    timestamp_valid,
    input  wire                    timestamp_edge_type,
    input  wire [COARSE_W+10:0]    timestamp_ps,

    output reg                     pulse_width_valid,
    output reg  [COARSE_W+10:0]    pulse_width_ps,
    output reg                     error_valid,
    output reg  [3:0]               error_code
);

    //============================================================
    // 参数与位宽：统一使用 ps
    //============================================================
    localparam integer TS_W  = COARSE_W + 11;
    localparam integer OUT_W = COARSE_W + 11;

    localparam [3:0] ERR_NONE        = 4'd0;
    localparam [3:0] ERR_DOUBLE_RISE = 4'd1;
    localparam [3:0] ERR_ORPHAN_FALL = 4'd2;
    localparam [3:0] ERR_TIME_RANGE  = 4'd3;

    // 粗计数器回卷周期：
    // 500 MHz -> 2000 ps/计数
    // COARSE_W=8 -> 256*2000 = 512000 ps
    localparam [TS_W-1:0] WRAP_PS =
        ({{(TS_W-1){1'b0}}, 1'b1} << COARSE_W) * 2000;

`ifndef SYNTHESIS
    initial begin
        if (COARSE_W < 1)
            $error("tdc_time_merge: COARSE_W must be >= 1");
    end
`endif

    //============================================================
    // Stage 1：缓存上升沿，接收下降沿并计算时间差
    //============================================================
    reg            rise_pending;
    reg [TS_W-1:0] rise_timestamp_ps;

    reg            s1_valid;
    reg [TS_W:0]   s1_diff;

    wire in_range = (timestamp_ps < WRAP_PS);

    wire [TS_W:0] diff_w =
        {1'b0, timestamp_ps} -
        {1'b0, rise_timestamp_ps};

    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            rise_pending      <= 1'b0;
            rise_timestamp_ps <= {TS_W{1'b0}};
            s1_valid          <= 1'b0;
            s1_diff           <= {(TS_W+1){1'b0}};
            error_valid       <= 1'b0;
            error_code        <= ERR_NONE;
        end else begin
            s1_valid    <= 1'b0;
            error_valid <= 1'b0;

            if (timestamp_valid) begin
                if (!in_range) begin
                    rise_pending <= 1'b0;
                    error_valid  <= 1'b1;
                    error_code   <= ERR_TIME_RANGE;
                end
                else if (timestamp_edge_type) begin
                    if (rise_pending) begin
                        error_valid <= 1'b1;
                        error_code  <= ERR_DOUBLE_RISE;
                    end

                    rise_timestamp_ps <= timestamp_ps;
                    rise_pending      <= 1'b1;
                end
                else if (rise_pending) begin
                    s1_diff      <= diff_w;
                    s1_valid     <= 1'b1;
                    rise_pending <= 1'b0;
                end
                else begin
                    error_valid <= 1'b1;
                    error_code  <= ERR_ORPHAN_FALL;
                end
            end
        end
    end

    //============================================================
    // Stage 2：回卷修正，结果仍为 ps
    //============================================================
    reg [TS_W-1:0] s2_width_ps;
    reg            s2_valid;

    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            s2_width_ps <= {TS_W{1'b0}};
            s2_valid    <= 1'b0;
        end else begin
            s2_valid <= s1_valid;

            if (s1_valid) begin
                if (s1_diff[TS_W])
                    // 下降沿时间戳小于上升沿时，执行模回卷
                    s2_width_ps <=
                        s1_diff[TS_W-1:0] + WRAP_PS;
                else
                    s2_width_ps <= s1_diff[TS_W-1:0];
            end
        end
    end

    //============================================================
    // Stage 3：输出脉宽，单位 ps，不再乘10
    //============================================================
    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            pulse_width_valid <= 1'b0;
            pulse_width_ps    <= {OUT_W{1'b0}};
        end else begin
            pulse_width_valid <= s2_valid;

            if (s2_valid)
                pulse_width_ps <= s2_width_ps;
        end
    end

endmodule
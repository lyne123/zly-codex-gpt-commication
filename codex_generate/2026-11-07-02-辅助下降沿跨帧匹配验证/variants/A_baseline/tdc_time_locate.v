`timescale 1ns/1ps

module tdc_time_locate #(
    parameter integer COARSE_W = 8,
    parameter integer MAX_TAP  = 64,
    parameter integer TAP_PS   = 10,
    // 偏移为正向时间戳的测量偏差，单位ps；默认0仅为未校准占位。
    parameter integer ENABLE_SKEW_COMP = 0,
    parameter signed [17:0] RISE_OFFSET_0_PS = 18'sd0,
    parameter signed [17:0] RISE_OFFSET_90_PS = 18'sd0,
    parameter signed [17:0] RISE_OFFSET_180_PS = 18'sd0,
    parameter signed [17:0] RISE_OFFSET_270_PS = 18'sd0,
    parameter signed [17:0] FALL_OFFSET_0_PS = 18'sd0,
    parameter signed [17:0] FALL_OFFSET_90_PS = 18'sd0,
    parameter signed [17:0] FALL_OFFSET_180_PS = 18'sd0,
    parameter signed [17:0] FALL_OFFSET_270_PS = 18'sd0
)(
    input  wire                    clk_500m,
    input  wire                    rst_n,
    input  wire                    edge_valid,
    input  wire                    edge_type_q,      // 1: rise, 0: fall
    input  wire [7:0]              chosen_code,
    input  wire [1:0]              sel_index,        // 0:90, 1:180, 2:270, 3:next 0
    input  wire                    polarity_conflict,
    input  wire                    repeat_error,    // reserved; not used here
    output reg                     timestamp_valid,
    output reg                     timestamp_edge_type,
    output reg [COARSE_W+10:0]     timestamp_ps
);
    localparam integer TIME_W = COARSE_W + 11;
    // 额外符号位覆盖18位偏移与中细时间之差，也兼容小粗计数器测试。
    localparam integer ARITH_W = (TIME_W+2 > 20) ? TIME_W+2 : 20;
    // One whole coarse-counter revolution, in ps (2000 ps per 500-MHz cycle).
    localparam [TIME_W-1:0] MODULO = {11'd2000, {COARSE_W{1'b0}}};
    localparam signed [ARITH_W-1:0] MODULO_EXT = {{(ARITH_W-TIME_W){1'b0}}, MODULO};

`ifndef SYNTHESIS
    function offset_in_range;
        input signed [17:0] value;
        reg signed [ARITH_W-1:0] expanded;
        begin
            expanded = value;
            // 留出一个中细周期的余量，确保单次加减MODULO即可归一化。
            offset_in_range = (expanded >= -MODULO_EXT+2000) &&
                              (expanded <= MODULO_EXT-2000);
        end
    endfunction
    initial begin
        if (COARSE_W < 1 || MAX_TAP < 1 || MAX_TAP > 255 ||
            TAP_PS < 10 || (TAP_PS % 10) != 0 ||
            MAX_TAP * TAP_PS > 2000)
            $error("tdc_time_locate: invalid parameter");
        if (ENABLE_SKEW_COMP != 0 &&
            !(offset_in_range(RISE_OFFSET_0_PS) && offset_in_range(RISE_OFFSET_90_PS) &&
              offset_in_range(RISE_OFFSET_180_PS) && offset_in_range(RISE_OFFSET_270_PS) &&
              offset_in_range(FALL_OFFSET_0_PS) && offset_in_range(FALL_OFFSET_90_PS) &&
              offset_in_range(FALL_OFFSET_180_PS) && offset_in_range(FALL_OFFSET_270_PS)))
            $fatal(1,"补偿偏移超出当前粗计数回卷范围");
    end
`endif

    // Free-running coarse counter; naturally wraps at 2**COARSE_W.
    reg [COARSE_W-1:0] coarse_counter;
    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n)
            coarse_counter <= {COARSE_W{1'b0}};
        else
            coarse_counter <= coarse_counter + 1'b1;
    end

    // Constant shift-and-add conversion from tap count directly to ps.
    function [10:0] taps_to_ps;
        input [7:0] taps;
        reg [21:0] acc;
        integer k;
        begin
            acc = 22'd0;
            for (k = 0; k < 11; k = k + 1)
                if ((TAP_PS >> k) & 1)
                    acc = acc + ({14'd0, taps} << k);
            taps_to_ps = acc[10:0];
        end
    endfunction

    // Stage 1: latch selected edge; invert fall code.
    reg       s1_valid, s1_type;
    reg [7:0] s1_tap;
    reg [1:0] s1_index;
    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            s1_valid <= 1'b0;
            s1_type  <= 1'b0;
            s1_tap   <= 8'd0;
            s1_index <= 2'd0;
        end else begin
            s1_valid <= edge_valid && !polarity_conflict &&
                        (chosen_code <= MAX_TAP);
            if (edge_valid && !polarity_conflict &&
                (chosen_code <= MAX_TAP)) begin
                s1_type  <= edge_type_q ? 1'b1 : 1'b0;
                s1_tap   <= edge_type_q ? chosen_code : (MAX_TAP - chosen_code);
                s1_index <= sel_index;
            end
        end
    end

    // Stage 2: select mid time, convert fine time and snapshot coarse.
    reg                    s2_valid, s2_type;
    reg [10:0]             s2_mid_time, s2_fine_time;
    reg [COARSE_W-1:0]     s2_coarse;
    reg signed [18:0]      s2_comp_mid;
    // sel_index不是物理TDL号：0/1/2/3对应90/180/270/下一周期0度。
    // 每项中测减偏移均为展开期常量，运行时只选择，不串联两次减法。
    function signed [18:0] selected_comp_mid;
        input [1:0] index;
        input is_rise;
        begin
            case (index)
                2'd0: selected_comp_mid = is_rise ? (19'sd500 - RISE_OFFSET_90_PS) : (19'sd500 - FALL_OFFSET_90_PS);
                2'd1: selected_comp_mid = is_rise ? (19'sd1000 - RISE_OFFSET_180_PS) : (19'sd1000 - FALL_OFFSET_180_PS);
                2'd2: selected_comp_mid = is_rise ? (19'sd1500 - RISE_OFFSET_270_PS) : (19'sd1500 - FALL_OFFSET_270_PS);
                2'd3: selected_comp_mid = is_rise ? (19'sd2000 - RISE_OFFSET_0_PS) : (19'sd2000 - FALL_OFFSET_0_PS);
            endcase
        end
    endfunction
    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            s2_valid     <= 1'b0;
            s2_type      <= 1'b0;
            s2_mid_time  <= 11'd0;
            s2_fine_time <= 11'd0;
            s2_coarse    <= {COARSE_W{1'b0}};
            s2_comp_mid  <= 19'sd0;
        end else begin
            s2_valid <= s1_valid;
            if (s1_valid) begin
                s2_type <= s1_type ? 1'b1 : 1'b0;
                case (s1_index)
                    2'd0: s2_mid_time <= 11'd500;
                    2'd1: s2_mid_time <= 11'd1000;
                    2'd2: s2_mid_time <= 11'd1500;
                    2'd3: s2_mid_time <= 11'd2000;
                endcase
                s2_fine_time <= taps_to_ps(s1_tap);
                s2_coarse    <= coarse_counter;
                s2_comp_mid  <= selected_comp_mid(s1_index, s1_type);
            end
        end
    end

    // Stage 3: two independent operations, latched in parallel.
    // C*2000 = C*(2048 - 32 - 16), shift/subtract only.
    wire [TIME_W-1:0] coarse_ext = {{11{1'b0}}, s2_coarse};
    wire [TIME_W-1:0] coarse_x2000 =
        (coarse_ext << 11) - ((coarse_ext << 5) + (coarse_ext << 4));
    wire signed [11:0] mid_minus_fine =
        $signed({1'b0, s2_mid_time}) - $signed({1'b0, s2_fine_time});
    wire signed [18:0] relative_adjusted;
    generate
        if (ENABLE_SKEW_COMP != 0) begin : g_skew_comp
            // 保持理想中测不变，只从正向时间戳减去已测偏移。
            assign relative_adjusted = s2_comp_mid - $signed({8'd0, s2_fine_time});
        end else begin : g_skew_bypass
            // 显式旁路与参数数值无关，保持原始5级流水及其时间戳。
            assign relative_adjusted = {{7{mid_minus_fine[11]}}, mid_minus_fine};
        end
    endgenerate

    reg                 s3_valid, s3_type;
    reg [TIME_W-1:0]    s3_coarse_time;
    reg signed [18:0]   s3_relative;
    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            s3_valid       <= 1'b0;
            s3_type        <= 1'b0;
            s3_coarse_time <= {TIME_W{1'b0}};
            s3_relative    <= 19'sd0;
        end else begin
            s3_valid <= s2_valid;
            if (s2_valid) begin
                s3_type        <= s2_type ? 1'b1 : 1'b0;
                s3_coarse_time <= coarse_x2000;
                s3_relative    <= relative_adjusted;
            end
        end
    end

    //==================================================
    // Stage 4：合并粗时间与中细时间，寄存原始时间戳
    //==================================================
    wire signed [ARITH_W-1:0] relative_ext =
        {{(ARITH_W-19){s3_relative[18]}}, s3_relative};

    wire signed [ARITH_W-1:0] sum_signed =
        $signed({{(ARITH_W-TIME_W){1'b0}}, s3_coarse_time}) + relative_ext;

    reg                       s4_valid, s4_type;
    reg signed [ARITH_W-1:0]   s4_sum;

    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            s4_valid <= 1'b0;
            s4_type  <= 1'b0;
            s4_sum   <= 0;
        end else begin
            s4_valid <= s3_valid;

            if (s3_valid) begin
                s4_type <= s3_type;
                s4_sum  <= sum_signed;
            end
        end
    end

    //==================================================
    // Stage 5：正常模回卷，输出最终时间戳
    //==================================================
    // MODULO=2000*2^COARSE_W=125*2^(COARSE_W+4)，回卷不改变低位。
    // 高位保持有符号运算；比较、加模数和减模数并行，避免低位进入宽比较链。
    localparam integer WRAP_LOW_W = COARSE_W + 4;
    localparam integer WRAP_HIGH_W = ARITH_W - WRAP_LOW_W;
    localparam signed [WRAP_HIGH_W-1:0] MODULO_HIGH = 125;
    wire signed [WRAP_HIGH_W-1:0] sum_high =
        $signed(s4_sum[ARITH_W-1:WRAP_LOW_W]);
    wire signed [WRAP_HIGH_W-1:0] wrap_add_high = sum_high + MODULO_HIGH;
    wire signed [WRAP_HIGH_W-1:0] wrap_sub_high = sum_high - MODULO_HIGH;
    wire signed [WRAP_HIGH_W-1:0] wrapped_high =
        sum_high[WRAP_HIGH_W-1] ? wrap_add_high :
        (sum_high >= MODULO_HIGH) ? wrap_sub_high : sum_high;
    wire signed [ARITH_W-1:0] wrapped_time =
        {wrapped_high, s4_sum[WRAP_LOW_W-1:0]};

    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            timestamp_valid     <= 1'b0;
            timestamp_edge_type <= 1'b0;
            timestamp_ps        <= 0;
        end else begin
            timestamp_valid <= s4_valid;

            if (s4_valid) begin
                timestamp_edge_type <= s4_type;
                timestamp_ps        <= wrapped_time[TIME_W-1:0];
            end else begin
                timestamp_edge_type <= 1'b0;
            end
        end
    end

endmodule

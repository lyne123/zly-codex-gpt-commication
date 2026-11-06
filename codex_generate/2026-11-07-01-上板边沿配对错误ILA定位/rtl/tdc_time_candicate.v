//============================================================
// 四相 TDC 候选选择与同极性相邻帧去重（5级流水，500MHz优化）
// 输入位序：{下一周期0°, 270°, 180°, 90°}
// 按时间定位码选择距中心值最近的有效候选；
// 下降沿先翻转再比较，等距时90° > 180° > 270° > 0°。
// 同极性相邻帧保留前者、丢弃后者；非相邻同极性保留并报repeat_error。
// chosen_code仍输出原始细测码，由后级tdc_time_locate完成下降沿翻转。
//============================================================
module tdc_time_candicate #(
    parameter [7:0] CENTER_CODE = 8'd32,
    parameter [7:0] MAX_TAP     = 8'd64
)(
    input  wire        clk_500m,
    input  wire        rst_n,
    input  wire        sync_valid,
    input  wire [31:0] all_fine_code,
    input  wire [3:0]  sync_edge_valid,
    input  wire [7:0]  sync_edge_polarity,

    output reg         edge_valid,
    output reg         edge_type_q,
    output reg [7:0]   chosen_code,
    output reg [1:0]   sel_index,
    output reg         polarity_conflict,
    output reg         repeat_error
);

    // [3]=下一周期0°, [2]=270°, [1]=180°, [0]=90°
    // 极性：11=上升沿, 10=下降沿; 输出edge_type_q: 1=上升沿

    //==================================================
    // Stage 1：输入锁存
    //==================================================
    reg        s1_valid;
    reg [31:0] s1_codes;
    reg [3:0]  s1_mask;
    reg [7:0]  s1_polarity;

    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            s1_valid    <= 1'b0;
            s1_codes    <= 32'd0;
            s1_mask     <= 4'd0;
            s1_polarity <= 8'd0;
        end else begin
            s1_valid    <= sync_valid;
            s1_codes    <= all_fine_code;
            s1_mask     <= sync_edge_valid;
            s1_polarity <= sync_edge_polarity;
        end
    end

    // 仅用于排序，绝不改变输出的chosen_code（避免后级重复翻转）。
    function [7:0] code_distance;
        input [7:0] code;
        input       is_rise;
        reg [7:0] effective_code;
        begin
            effective_code = is_rise ? code : (MAX_TAP - code);
            if (effective_code >= CENTER_CODE)
                code_distance = effective_code - CENTER_CODE;
            else
                code_distance = CENTER_CODE - effective_code;
        end
    endfunction

    //==================================================
    // Stage 2：极性筛选、混合极性冲突、计算4路距离
    //==================================================
    wire [3:0] rise_mask_w = s1_mask & {
        (s1_polarity[7:6] == 2'b11),
        (s1_polarity[5:4] == 2'b11),
        (s1_polarity[3:2] == 2'b11),
        (s1_polarity[1:0] == 2'b11)
    } & {4{s1_valid}};

    wire [3:0] fall_mask_w = s1_mask & {
        (s1_polarity[7:6] == 2'b10),
        (s1_polarity[5:4] == 2'b10),
        (s1_polarity[3:2] == 2'b10),
        (s1_polarity[1:0] == 2'b10)
    } & {4{s1_valid}};

    wire [3:0] valid_mask_w = rise_mask_w | fall_mask_w;

    reg [31:0] s2_codes;
    reg [3:0]  s2_mask;
    reg [3:0]  s2_rise_mask;
    reg        s2_conflict;
    reg [7:0]  s2_dist0, s2_dist1, s2_dist2, s2_dist3;

    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            s2_codes     <= 32'd0;
            s2_mask      <= 4'd0;
            s2_rise_mask <= 4'd0;
            s2_conflict  <= 1'b0;
            s2_dist0    <= 8'd0;
            s2_dist1    <= 8'd0;
            s2_dist2    <= 8'd0;
            s2_dist3    <= 8'd0;
        end else begin
            s2_codes     <= s1_codes;
            s2_mask      <= valid_mask_w;
            s2_rise_mask <= rise_mask_w;
            s2_conflict  <= (|rise_mask_w) && (|fall_mask_w);
            s2_dist0    <= code_distance(s1_codes[7:0],   rise_mask_w[0]);
            s2_dist1    <= code_distance(s1_codes[15:8],  rise_mask_w[1]);
            s2_dist2    <= code_distance(s1_codes[23:16], rise_mask_w[2]);
            s2_dist3    <= code_distance(s1_codes[31:24], rise_mask_w[3]);
        end
    end

    //==================================================
    // Stage 3：仅在各组内部进行1次比较并寄存组优胜者
    // pair01: 90° / 180°，pair23: 270° / 下一周期0°
    //==================================================
    wire pair01_valid_w = |s2_mask[1:0];
    wire pair23_valid_w = |s2_mask[3:2];
    wire choose0_w = s2_mask[0] &&
                     (!s2_mask[1] || (s2_dist0 <= s2_dist1));
    wire choose2_w = s2_mask[2] &&
                     (!s2_mask[3] || (s2_dist2 <= s2_dist3));

    reg        s3_valid, s3_conflict;
    reg        s3_pair01_valid, s3_pair23_valid;
    reg [7:0]  s3_pair01_dist, s3_pair23_dist;
    reg [7:0]  s3_pair01_code, s3_pair23_code;
    reg [1:0]  s3_pair01_index, s3_pair23_index;
    reg        s3_pair01_type, s3_pair23_type;

    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            s3_valid        <= 1'b0;
            s3_conflict     <= 1'b0;
            s3_pair01_valid <= 1'b0;
            s3_pair23_valid <= 1'b0;
            s3_pair01_dist  <= 8'd0;
            s3_pair23_dist  <= 8'd0;
            s3_pair01_code  <= 8'd0;
            s3_pair23_code  <= 8'd0;
            s3_pair01_index <= 2'd0;
            s3_pair23_index <= 2'd0;
            s3_pair01_type  <= 1'b0;
            s3_pair23_type  <= 1'b0;
        end else begin
            s3_valid        <= (|s2_mask) && !s2_conflict;
            s3_conflict     <= s2_conflict;
            s3_pair01_valid <= pair01_valid_w;
            s3_pair23_valid <= pair23_valid_w;

            if (choose0_w) begin
                s3_pair01_dist  <= s2_dist0;
                s3_pair01_code  <= s2_codes[7:0];
                s3_pair01_index <= 2'd0;
                s3_pair01_type  <= s2_rise_mask[0];
            end else begin
                s3_pair01_dist  <= s2_dist1;
                s3_pair01_code  <= s2_codes[15:8];
                s3_pair01_index <= 2'd1;
                s3_pair01_type  <= s2_rise_mask[1];
            end

            if (choose2_w) begin
                s3_pair23_dist  <= s2_dist2;
                s3_pair23_code  <= s2_codes[23:16];
                s3_pair23_index <= 2'd2;
                s3_pair23_type  <= s2_rise_mask[2];
            end else begin
                s3_pair23_dist  <= s2_dist3;
                s3_pair23_code  <= s2_codes[31:24];
                s3_pair23_index <= 2'd3;
                s3_pair23_type  <= s2_rise_mask[3];
            end
        end
    end

    //==================================================
    // Stage 4：仅比较两组优胜者，寄存最终候选
    //==================================================
    wire choose01_w = s3_pair01_valid &&
                      (!s3_pair23_valid ||
                       (s3_pair01_dist <= s3_pair23_dist));

    reg       s4_valid, s4_type;
    reg [7:0] s4_code;
    reg [1:0] s4_index;
    reg       s4_conflict;

    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            s4_valid    <= 1'b0;
            s4_type     <= 1'b0;
            s4_code     <= 8'd0;
            s4_index    <= 2'd0;
            s4_conflict <= 1'b0;
        end else begin
            s4_valid    <= s3_valid;
            s4_conflict <= s3_conflict;
            if (s3_valid) begin
                if (choose01_w) begin
                    s4_code  <= s3_pair01_code;
                    s4_index <= s3_pair01_index;
                    s4_type  <= s3_pair01_type;
                end else begin
                    s4_code  <= s3_pair23_code;
                    s4_index <= s3_pair23_index;
                    s4_type  <= s3_pair23_type;
                end
            end else begin
                s4_code  <= 8'd0;
                s4_index <= 2'd0;
                s4_type  <= 1'b0;
            end
        end
    end

    //==================================================
    // Stage 5：保持原逻辑的相邻同极性去重、错误标志、寄存输出
    //==================================================
    reg prev_valid;
    reg prev_type;
    reg last_valid;
    reg last_type;

    wire duplicate_w = s4_valid && prev_valid &&
                       (s4_type == prev_type);
    wire repeat_w = s4_valid && last_valid &&
                    (s4_type == last_type) && !duplicate_w;
    wire emit_w = s4_valid && !duplicate_w;

    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) begin
            prev_valid        <= 1'b0;
            prev_type         <= 1'b0;
            last_valid        <= 1'b0;
            last_type         <= 1'b0;
            edge_valid        <= 1'b0;
            edge_type_q       <= 1'b0;
            chosen_code       <= 8'd0;
            sel_index         <= 2'd0;
            polarity_conflict <= 1'b0;
            repeat_error      <= 1'b0;
        end else begin
            prev_valid <= s4_valid;
            if (s4_valid)
                prev_type <= s4_type;
            if (s4_valid) begin
                last_valid <= 1'b1;
                last_type  <= s4_type;
            end

            edge_valid        <= emit_w;
            polarity_conflict <= s4_conflict;
            repeat_error      <= repeat_w;
            if (emit_w) begin
                edge_type_q <= s4_type;
                chosen_code <= s4_code;
                sel_index   <= s4_index;
            end else begin
                edge_type_q <= 1'b0;
                chosen_code <= 8'd0;
                sel_index   <= 2'd0;
            end
        end
    end
endmodule

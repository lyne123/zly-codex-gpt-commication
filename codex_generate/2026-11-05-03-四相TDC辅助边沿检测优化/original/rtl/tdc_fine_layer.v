`timescale 1ps/1ps
//======================================================================
// 四相 TDC 细测模块：三条数据通路并行，最后统一输出
// ① PWM → TDL采样 → 计1编码 ─────────────────→ 四相汇聚 → 码值输出
// ② PWM → TDL采样 → 极性识别 → 码值二次筛选 → 四相汇聚 ─┐
// ③ PWM → 0°采样 → 边沿检测 → 延迟对齐 ────────────────┤
//                                             联合判断 → 有效位/极性输出
// 四相顺序：90°、180°、270°、下一周期0°；输出位序高→低：
//             {下一周期0°，270°，180°，90°}
// 0°支路刻意少一级寄存器，保留原工程采样帧定义。
//======================================================================
module tdc_fine_layer #(
    parameter integer CARRY_NUM     = 16,
    parameter integer MAX_VALID_TAP = 60,
    parameter integer MIN_VALID_TAP = 5,
    parameter integer PWM_DIST_ENABLE = 1  // 1: 对称LUT树形PWM分发；0: 原始直连对照
)(
    input  wire        clk_500m,
    input  wire        clk_500m_deg90,
    input  wire        clk_500m_deg180,
    input  wire        clk_500m_deg270,
    input  wire        rst_n,
    input  wire        pwm_in,
    output reg [31:0]  all_fine_code,       // 每相8位，原始计1码
    output reg [3:0]   sync_edge_valid,     // 每相1位，联合判断后的有效标志
    output reg [7:0]   sync_edge_polarity,  // 每相2位：11上升、10下降、00无效
    output reg         sync_valid          // 四相数据流水线准备完成
);

    // Asynchronous reset assertion, synchronous release in each phase domain.
    (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg [1:0] rst_sync_0;
    (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg [1:0] rst_sync_90;
    (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg [1:0] rst_sync_180;
    (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg [1:0] rst_sync_270;

    always @(posedge clk_500m or negedge rst_n) begin
        if (!rst_n) rst_sync_0 <= 2'b00;
        else        rst_sync_0 <= {rst_sync_0[0], 1'b1};
    end
    always @(posedge clk_500m_deg90 or negedge rst_n) begin
        if (!rst_n) rst_sync_90 <= 2'b00;
        else        rst_sync_90 <= {rst_sync_90[0], 1'b1};
    end
    always @(posedge clk_500m_deg180 or negedge rst_n) begin
        if (!rst_n) rst_sync_180 <= 2'b00;
        else        rst_sync_180 <= {rst_sync_180[0], 1'b1};
    end
    always @(posedge clk_500m_deg270 or negedge rst_n) begin
        if (!rst_n) rst_sync_270 <= 2'b00;
        else        rst_sync_270 <= {rst_sync_270[0], 1'b1};
    end

    wire rst_n_0   = rst_sync_0[1];
    wire rst_n_90  = rst_sync_90[1];
    wire rst_n_180 = rst_sync_180[1];
    wire rst_n_270 = rst_sync_270[1];

    //==================================================================
    // 1. 主测量通路：PWM → 四相TDL采样 → 计1编码
    //    极性检测与编码使用同一次温度计码采样，互相并行。
    //==================================================================
    wire [7:0] code0, code90, code180, code270;
    wire [1:0] type0, type90, type180, type270;
    wire ready0, ready90, ready180, ready270;

    //==================================================================
    // PWM 对称树形分发（对应示意图 B0 -> B1 -> B2 的四端点简化形式）
    //                pwm_in
    //                   |
    //                  B0           公共一级
    //               /      \
    //             B1_0     B1_1     对称二级
    //            /   \    /   \
    //          B2_0 B2_1 B2_2 B2_3  对称末级
    //           |    |    |    |
    //           0°  90°  180° 270°  四条TDL的第一个CARRY4.CYINIT
    // 所有TDL输入具有相同的LUT1级数，且每个末级LUT仅驱动一条链。
    // DONT_TOUCH保护显式缓冲级；真正的低偏斜还需物理位置约束及布线验证。
    // 注意：不修改下方辅助边沿检测的pwm_in，以免改变其原始对齐拍数。
    //==================================================================
    (* KEEP="TRUE" *) wire pwm_b0;
    (* KEEP="TRUE" *) wire [1:0] pwm_b1;
    (* KEEP="TRUE" *) wire [3:0] pwm_tdl;

    generate
        if (PWM_DIST_ENABLE != 0) begin : g_pwm_dist
            // LUT1 INIT=2'b10：O=I0，纯组合缓冲，无时钟周期延迟。
            (* DONT_TOUCH="TRUE" *) LUT1 #(.INIT(2'b10)) u_pwm_b0 (
                .I0(pwm_in), .O(pwm_b0)
            );
            (* DONT_TOUCH="TRUE" *) LUT1 #(.INIT(2'b10)) u_pwm_b1_0 (
                .I0(pwm_b0), .O(pwm_b1[0])
            );
            (* DONT_TOUCH="TRUE" *) LUT1 #(.INIT(2'b10)) u_pwm_b1_1 (
                .I0(pwm_b0), .O(pwm_b1[1])
            );
            (* DONT_TOUCH="TRUE" *) LUT1 #(.INIT(2'b10)) u_pwm_b2_0 (
                .I0(pwm_b1[0]), .O(pwm_tdl[0])
            );
            (* DONT_TOUCH="TRUE" *) LUT1 #(.INIT(2'b10)) u_pwm_b2_1 (
                .I0(pwm_b1[0]), .O(pwm_tdl[1])
            );
            (* DONT_TOUCH="TRUE" *) LUT1 #(.INIT(2'b10)) u_pwm_b2_2 (
                .I0(pwm_b1[1]), .O(pwm_tdl[2])
            );
            (* DONT_TOUCH="TRUE" *) LUT1 #(.INIT(2'b10)) u_pwm_b2_3 (
                .I0(pwm_b1[1]), .O(pwm_tdl[3])
            );
        end else begin : g_pwm_direct
            assign pwm_b0 = pwm_in;
            assign pwm_b1 = {2{pwm_in}};
            assign pwm_tdl = {4{pwm_in}};
        end
    endgenerate

    tdc_phase_tdl_encoder #(
        .CARRY_NUM(CARRY_NUM), .MAX_VALID_TAP(MAX_VALID_TAP), .MIN_VALID_TAP(MIN_VALID_TAP)
    ) u_tdl0 (
        .clk(clk_500m), .rst_n(rst_n_0), .pwm_in(pwm_tdl[0]),
        .code(code0), .code_valid(ready0), .edge_type(type0)
    );

    tdc_phase_tdl_encoder #(
        .CARRY_NUM(CARRY_NUM), .MAX_VALID_TAP(MAX_VALID_TAP), .MIN_VALID_TAP(MIN_VALID_TAP)
    ) u_tdl90 (
        .clk(clk_500m_deg90), .rst_n(rst_n_90), .pwm_in(pwm_tdl[1]),
        .code(code90), .code_valid(ready90), .edge_type(type90)
    );

    tdc_phase_tdl_encoder #(
        .CARRY_NUM(CARRY_NUM), .MAX_VALID_TAP(MAX_VALID_TAP), .MIN_VALID_TAP(MIN_VALID_TAP)
    ) u_tdl180 (
        .clk(clk_500m_deg180), .rst_n(rst_n_180), .pwm_in(pwm_tdl[2]),
        .code(code180), .code_valid(ready180), .edge_type(type180)
    );

    tdc_phase_tdl_encoder #(
        .CARRY_NUM(CARRY_NUM), .MAX_VALID_TAP(MAX_VALID_TAP), .MIN_VALID_TAP(MIN_VALID_TAP)
    ) u_tdl270 (
        .clk(clk_500m_deg270), .rst_n(rst_n_270), .pwm_in(pwm_tdl[3]),
        .code(code270), .code_valid(ready270), .edge_type(type270)
    );

    //==================================================================
    // 2. 极性检测通路：温度计码 → 极性识别 → 二次筛选
    //    已在各个 tdc_phase_tdl_encoder 中完成：
    //    11=上升、10=下降、00=无候选，原始计1码必须在1～55之间。
    //    typeX 与 codeX 均对应同一次采样，后续一起跨相位传输。
    //==================================================================
    // 每相10位数据包：{2位候选极性, 8位计1码}。
    // “是否流水线准备完成”由下方独立的 ready 信号传送。
    wire [9:0] pack0   = {type0,   code0};
    wire [9:0] pack90  = {type90,  code90};
    wire [9:0] pack180 = {type180, code180};
    wire [9:0] pack270 = {type270, code270};

    //==================================================================
    // 3. 四相跨相位传输：统一到0°时钟域
    //    四相数据始终按整包传输，避免计数码和极性错拍。
    //==================================================================
    // 3.1 270° → 180°（同频移相时钟，必须通过STA验证）
    reg [9:0] pack270_to180;
    reg       ready270_to180;
    always @(posedge clk_500m_deg180) begin
        pack270_to180 <= pack270;
    end
    always @(posedge clk_500m_deg180 or negedge rst_n_180) begin
        if (!rst_n_180) ready270_to180 <= 1'b0;
        else        ready270_to180 <= ready270;
    end

    // 3.2 180° → 90°；270°经180° → 90°
    reg [9:0] pack180_to90, pack270_to90;
    reg       ready180_to90, ready270_to90;
    always @(posedge clk_500m_deg90) begin
        pack180_to90 <= pack180;
        pack270_to90 <= pack270_to180;
    end
    always @(posedge clk_500m_deg90 or negedge rst_n_90) begin
        if (!rst_n_90) begin
            ready180_to90 <= 1'b0;
            ready270_to90 <= 1'b0;
        end else begin
            ready180_to90 <= ready180;
            ready270_to90 <= ready270_to180;
        end
    end

    // 3.3 0°域对齐寄存器。保留0°支路故意少打一拍。
    reg [9:0] pack0_d1;
    reg [9:0] pack90_d1, pack90_d2;
    reg [9:0] pack180_d1;
    reg ready0_d1;
    reg ready90_d1, ready90_d2;
    reg ready180_d1;

    always @(posedge clk_500m) begin
        pack0_d1   <= pack0;
        pack90_d1  <= pack90;
        pack90_d2  <= pack90_d1;
        pack180_d1 <= pack180_to90;
    end

    always @(posedge clk_500m or negedge rst_n_0) begin
        if (!rst_n_0) begin
            ready0_d1   <= 1'b0;
            ready90_d1  <= 1'b0;
            ready90_d2  <= 1'b0;
            ready180_d1 <= 1'b0;
        end else begin
            ready0_d1   <= ready0;
            ready90_d1  <= ready90;
            ready90_d2  <= ready90_d1;
            ready180_d1 <= ready180_to90;
        end
    end

    wire frame_ready = ready0_d1 & ready90_d2 & ready180_d1 & ready270_to90;

    //==================================================================
    // 4. 辅助通路：PWM → 0°双级同步 → 边沿检测 → 延迟对齐
    //==================================================================
    (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg pwm_meta, pwm_sync;
    reg pwm_history;
    always @(posedge clk_500m or negedge rst_n_0) begin
        if (!rst_n_0) begin
            pwm_meta    <= 1'b0;
            pwm_sync    <= 1'b0;
            pwm_history <= 1'b0;
        end else begin
            pwm_meta    <= pwm_in;
            pwm_sync    <= pwm_meta;
            pwm_history <= pwm_sync;
        end
    end
    wire aux_rise =  pwm_sync & ~pwm_history;
    wire aux_fall = ~pwm_sync &  pwm_history;

    // 匹配上述采样帧在最终0°输出寄存器之前的辅助脉冲。
    // CARRY_NUM=16时对应bit4；属于RTL推导值，需仿真验证边界行为。
    // 编码器输出新增同相位寄存级，辅助门控同步延后一拍，窗口宽度不变。
    localparam integer AUX_GATE_INDEX = 6;
    reg [AUX_GATE_INDEX+1:0] aux_rise_pipe, aux_fall_pipe;
    always @(posedge clk_500m or negedge rst_n_0) begin
        if (!rst_n_0) begin
            aux_rise_pipe <= {(AUX_GATE_INDEX+2){1'b0}};
            aux_fall_pipe <= {(AUX_GATE_INDEX+2){1'b0}};
        end else begin
            aux_rise_pipe <= {aux_rise_pipe[AUX_GATE_INDEX:0], aux_rise};
            aux_fall_pipe <= {aux_fall_pipe[AUX_GATE_INDEX:0], aux_fall};
        end
    end
    // 允许辅助边沿相对原匹配位置延迟1拍
    wire aux_rise_match =
                        aux_rise_pipe[AUX_GATE_INDEX] |
                        aux_rise_pipe[AUX_GATE_INDEX-1];

    wire aux_fall_match =
                        aux_fall_pipe[AUX_GATE_INDEX] |
                        aux_fall_pipe[AUX_GATE_INDEX-1];
    //==================================================================
    // 5. 联合判断：TDL极性与PWM辅助检测一致才判为有效
    //    判别结果及原始码在同一个0°上升沿寄存后输出。
    //==================================================================
    function [1:0] confirm_edge;
        input [1:0] tdl_type;
        input       aux_up;
        input       aux_down;
        begin
            if ((tdl_type == 2'b11) && aux_up)
                confirm_edge = 2'b11;
            else if ((tdl_type == 2'b10) && aux_down)
                confirm_edge = 2'b10;
            else
                confirm_edge = 2'b00;
        end
    endfunction

    wire [1:0] final_type0   = confirm_edge(pack0_d1[9:8],        aux_rise_match, aux_fall_match);
    wire [1:0] final_type90  = confirm_edge(pack90_d2[9:8],       aux_rise_match, aux_fall_match);
    wire [1:0] final_type180 = confirm_edge(pack180_d1[9:8],      aux_rise_match, aux_fall_match);
    wire [1:0] final_type270 = confirm_edge(pack270_to90[9:8],    aux_rise_match, aux_fall_match);

    always @(posedge clk_500m or negedge rst_n_0) begin
        if (!rst_n_0) begin
            all_fine_code      <= 32'd0;
            sync_edge_valid    <= 4'd0;
            sync_edge_polarity <= 8'd0;
            sync_valid         <= 1'b0;
        end else begin
            // 位序：{下一周期0°，270°，180°，90°}
            all_fine_code <= {
                pack0_d1[7:0],
                pack270_to90[7:0],
                pack180_d1[7:0],
                pack90_d2[7:0]
            };
            sync_valid <= frame_ready;
            sync_edge_polarity <= frame_ready ? {
                final_type0, final_type270, final_type180, final_type90
            } : 8'd0;
            sync_edge_valid <= frame_ready ? {
                (final_type0   != 2'b00),
                (final_type270 != 2'b00),
                (final_type180 != 2'b00),
                (final_type90  != 2'b00)
            } : 4'd0;
        end
    end
endmodule

//======================================================================
// 单相 TDL：四相各实例化一个
// 内部并行执行：采样后计1编码 / 采样后极性判断；最终码值筛选一次。
//======================================================================
module tdc_phase_tdl_encoder #(
    parameter integer CARRY_NUM     = 16,
    parameter integer MAX_VALID_TAP = 55,
    parameter integer MIN_VALID_TAP = 10
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       pwm_in,
    output wire [7:0] code,
    output wire       code_valid,
    output wire [1:0] edge_type
);
    localparam integer TAPS    = CARRY_NUM * 4;
    localparam integer LEVELS  = $clog2(CARRY_NUM);
    localparam integer DEPTH   = LEVELS + 2;
    localparam integer CODE_W  = $clog2(TAPS + 1);

`ifndef SYNTHESIS
    initial begin
        if (CARRY_NUM < 1 || CARRY_NUM > 63 || MAX_VALID_TAP < 1 ||
            MAX_VALID_TAP >= TAPS || MIN_VALID_TAP < 1 || MIN_VALID_TAP >= MAX_VALID_TAP)
            $fatal(1, "CARRY_NUM/MAX_VALID_TAP/MIN_VALID_TAP参数不合法");
    end
`endif

    // 1. rst_n 已由 tdc_fine_layer 在本时钟域同步释放。
    // 2. 数据流水线准备完成标志
    reg [DEPTH-1:0] ready_pipe;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) ready_pipe <= {DEPTH{1'b0}};
        else              ready_pipe <= {ready_pipe[DEPTH-2:0], 1'b1};
    end
    wire encoder_ready = ready_pipe[DEPTH-1];
    reg output_ready;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) output_ready <= 1'b0;
        else        output_ready <= encoder_ready;
    end
    assign code_valid = output_ready;

    // 3. CARRY4延迟链与采样寄存器
    (* KEEP="TRUE", DONT_TOUCH="TRUE" *) wire [TAPS-1:0] carry_tap;
    wire [CARRY_NUM:0] carry_link;
    assign carry_link[0] = 1'b0;

    genvar i, lev, j;
    generate
        for (i=0; i<CARRY_NUM; i=i+1) begin : g_carry
            (* DONT_TOUCH="TRUE" *) CARRY4 u_carry4 (
                .CO(carry_tap[4*i +: 4]),
                .O(),
                .CI(carry_link[i]),
                .CYINIT((i == 0) ? pwm_in : 1'b0),
                .DI(4'b0000),
                .S(4'b1111)
            );
            assign carry_link[i+1] = carry_tap[4*i+3];
        end
    endgenerate

    (* DONT_TOUCH="TRUE", SHREG_EXTRACT="NO" *) reg [TAPS-1:0] thermo_q;
    always @(posedge clk) thermo_q <= carry_tap;

    // 4. 通路一：并行计1编码（每4个tap先相加，再逐级合并）
    generate
        for (lev=0; lev<=LEVELS; lev=lev+1) begin : g_sum
            localparam integer NODES = (CARRY_NUM + (1 << lev) - 1) >> lev;
            localparam integer PREV_NODES = (lev == 0) ? 0 :
                ((CARRY_NUM + (1 << (lev-1)) - 1) >> (lev-1));
            localparam integer W = $clog2((4 << lev) + 1);
            reg [W-1:0] sum [0:NODES-1];
            for (j=0; j<NODES; j=j+1) begin : g_node
                if (lev == 0) begin : g_count4
                    always @(posedge clk)
                        sum[j] <= {2'b00, thermo_q[4*j+0]}
                                + {2'b00, thermo_q[4*j+1]}
                                + {2'b00, thermo_q[4*j+2]}
                                + {2'b00, thermo_q[4*j+3]};
                end else if (2*j+1 < PREV_NODES) begin : g_add2
                    always @(posedge clk)
                        sum[j] <= g_sum[lev-1].sum[2*j]
                                + g_sum[lev-1].sum[2*j+1];
                end else begin : g_pass
                    always @(posedge clk)
                        sum[j] <= g_sum[lev-1].sum[2*j];
                end
            end
        end
    endgenerate
    wire [7:0] code_raw = {{(8-CODE_W){1'b0}}, g_sum[LEVELS].sum[0]};

    // 5. 通路二：温度计码首尾判断极性，流水线对齐到code
    wire [1:0] detected_type;
    tdl_edge_candidate #(.TAPS(TAPS)) u_edge_candidate (
        .thermo(thermo_q), .edge_type(detected_type)
    );

    reg [2*(LEVELS+1)-1:0] type_pipe;
    always @(posedge clk) begin
        type_pipe <= (type_pipe << 2) | detected_type;
    end

    
    // 6. 二次判别：根据边沿极性分别设置有效码范围
    // 上升沿(11)：1～MAX_VALID_TAP，默认5~55
    // 下降沿(10)：MIN_VALID_TAP～TAPS-1，默认10～59
    // 其他极性或越界码均判为无效

    wire [1:0] raw_edge_type = type_pipe[2*LEVELS +: 2];

    wire code_in_range =
        ((raw_edge_type == 2'b11) &&
         (code_raw >= 8'd1) && (code_raw <= MAX_VALID_TAP)) ||
        ((raw_edge_type == 2'b10) &&
         (code_raw >= MIN_VALID_TAP) && (code_raw < TAPS));

    // 范围判定留在本相位2ns预算内，跨相位只传递已寄存的整包。
    // code、type和ready同时延迟一拍，不改变码值、极性或有效范围。
    reg [7:0] code_q;
    reg [1:0] edge_type_q;
    always @(posedge clk) begin
        code_q <= code_raw;
        edge_type_q <= (encoder_ready && code_in_range) ? raw_edge_type : 2'b00;
    end
    assign code = code_q;
    assign edge_type = edge_type_q;

endmodule

//======================================================================
// TDL极性检测：只做首尾多数判决，不负责计1编码和相位同步。
// thermo[0]靠近输入端；11上升、10下降、00无候选。
//======================================================================
module tdl_edge_candidate #(
    parameter integer TAPS = 64
)(
    input  wire [TAPS-1:0] thermo,
    output wire [1:0] edge_type
);
    wire rise, fall;

    function majority4;
        input [3:0] d;
        begin
            majority4 = (d[0] & d[1] & d[2]) |
                        (d[0] & d[1] & d[3]) |
                        (d[0] & d[2] & d[3]) |
                        (d[1] & d[2] & d[3]);
        end
    endfunction

    generate
        if (TAPS >= 8) begin : g_majority
            wire [3:0] head = thermo[3:0];
            wire [3:0] tail = thermo[TAPS-1:TAPS-4];
            assign rise = majority4(head)  & majority4(~tail);
            assign fall = majority4(~head) & majority4(tail);
        end else begin : g_short_chain
            assign rise =  thermo[0] & ~thermo[TAPS-1];
            assign fall = ~thermo[0] &  thermo[TAPS-1];
        end
    endgenerate

    assign edge_type = rise ? 2'b11 :
                       fall ? 2'b10 : 2'b00;
endmodule

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
    parameter integer PWM_DIST_ENABLE = 1, // 1: 对称LUT树形PWM分发；0: 原始直连对照
    parameter integer ENABLE_AUX_4PHASE = 1 // 0: 原单相辅助通路；1: 四相有序采样
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
    wire [7:0] guarded_final_types;
    wire [7:0] guarded_output_types;

    //==================================================================
    // 4. 辅助通路：四相独立采样 → 相关时钟固定延迟传输 → 有序边沿归属
    //==================================================================
    wire [3:0] aux_rise_match, aux_fall_match;
    wire pwm_aux_in = pwm_in;
    generate if (ENABLE_AUX_4PHASE == 0) begin : g_aux_legacy
    // 保留原单相逻辑及其匹配位置，供同一份 RTL 做 A/B 对照。
    (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg pwm_meta, pwm_sync;
    reg pwm_history;
    always @(posedge clk_500m or negedge rst_n_0) begin
        if (!rst_n_0) begin
            pwm_meta    <= 1'b0;
            pwm_sync    <= 1'b0;
            pwm_history <= 1'b0;
        end else begin
            pwm_meta    <= pwm_aux_in;
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
    wire legacy_rise_match =
                        aux_rise_pipe[AUX_GATE_INDEX] |
                        aux_rise_pipe[AUX_GATE_INDEX-1];

    wire legacy_fall_match =
                        aux_fall_pipe[AUX_GATE_INDEX] |
                        aux_fall_pipe[AUX_GATE_INDEX-1];
    assign aux_rise_match = {4{legacy_rise_match}};
    assign aux_fall_match = {4{legacy_fall_match}};
    end else begin : g_aux_4phase
        wire [3:0] phase_clk = {clk_500m_deg270,clk_500m_deg180,clk_500m_deg90,clk_500m};
        wire [3:0] phase_rst_n = {rst_n_270,rst_n_180,rst_n_90,rst_n_0};
        wire [3:0] sampled_level, sample_ready;
        wire [3:0] aux_rise_phase, aux_fall_phase;
        genvar phase;
        for (phase=0; phase<4; phase=phase+1) begin : g_phase
            (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg pwm_meta, pwm_sync;
            reg pwm_history;
            reg [2:0] warmup;
            always @(posedge phase_clk[phase] or negedge phase_rst_n[phase]) begin
                if (!phase_rst_n[phase]) begin
                    pwm_meta <= 1'b0;
                    pwm_sync <= 1'b0;
                    pwm_history <= 1'b0;
                    warmup <= 3'b000;
                end else begin
                    pwm_meta <= pwm_aux_in;
                    pwm_sync <= pwm_meta;
                    pwm_history <= pwm_sync;
                    warmup <= {warmup[1:0],1'b1};
                end
            end
            assign sampled_level[phase] = pwm_history;
            assign sample_ready[phase] = warmup[2];
            assign aux_rise_phase[phase] = pwm_sync & ~pwm_history;
            assign aux_fall_phase[phase] = ~pwm_sync & pwm_history;
        end

        // 传输电平记录而非异步 OR 脉冲，也不依赖 Toggle 的最小翻转间隔。
        // 所有跨相位跳转均沿 270→180→90→0，最短名义建立预算为 1.5ns。
        // 两位记录同时传递有效标志和采样电平；同相位补拍组成同一采样帧。
        reg [1:0] rec270_to180, rec270_to90, rec180_to90;
        reg [1:0] rec0_d1, rec0_d2;
        reg [1:0] rec90_d1, rec90_d2, rec90_d3;
        reg [1:0] rec180_d1, rec180_d2, rec270_d1;
        always @(posedge clk_500m_deg180 or negedge rst_n_180)
            if (!rst_n_180) rec270_to180 <= 2'b00;
            else rec270_to180 <= {sample_ready[3],sampled_level[3]};
        always @(posedge clk_500m_deg90 or negedge rst_n_90) begin
            if (!rst_n_90) begin
                rec270_to90 <= 2'b00;
                rec180_to90 <= 2'b00;
            end else begin
                rec270_to90 <= rec270_to180;
                rec180_to90 <= {sample_ready[2],sampled_level[2]};
            end
        end
        always @(posedge clk_500m or negedge rst_n_0) begin
            if (!rst_n_0) begin
                rec0_d1 <= 0; rec0_d2 <= 0;
                rec90_d1 <= 0; rec90_d2 <= 0; rec90_d3 <= 0;
                rec180_d1 <= 0; rec180_d2 <= 0; rec270_d1 <= 0;
            end else begin
                rec0_d1 <= {sample_ready[0],sampled_level[0]};
                rec0_d2 <= rec0_d1;
                rec90_d1 <= {sample_ready[1],sampled_level[1]};
                rec90_d2 <= rec90_d1;
                rec90_d3 <= rec90_d2;
                rec180_d1 <= rec180_to90;
                rec180_d2 <= rec180_d1;
                rec270_d1 <= rec270_to90;
            end
        end
        // 位0..3按真实采样先后排列：90°、180°、270°、下一周期0°。
        // 比较连续采样值，同一物理边沿只有一个0→1或1→0位置，无合并计时窗。
        wire [3:0] ordered_samples = {rec0_d2[0],rec270_d1[0],rec180_d2[0],rec90_d3[0]};
        wire ordered_ready = rec0_d2[1] & rec270_d1[1] & rec180_d2[1] & rec90_d3[1];
        reg previous_sample, armed;
        reg [3:0] aux_rise_slots, aux_fall_slots;
        wire [3:0] previous_slots = {ordered_samples[2:0],previous_sample};
        wire aux_rise_event = |aux_rise_slots;
        wire aux_fall_event = |aux_fall_slots;
        always @(posedge clk_500m or negedge rst_n_0) begin
            if (!rst_n_0) begin
                previous_sample <= 0;
                armed <= 0;
                aux_rise_slots <= 0;
                aux_fall_slots <= 0;
            end else begin
                armed <= ordered_ready;
                previous_sample <= ordered_samples[3];
                aux_rise_slots <= (armed && ordered_ready) ? (ordered_samples & ~previous_slots) : 4'b0000;
                aux_fall_slots <= (armed && ordered_ready) ? (~ordered_samples & previous_slots) : 4'b0000;
            end
        end

        // thermo→code_q 为 LEVELS+2 拍，原四相输出为采样帧后 LEVELS+5 拍。
        // 本通路含 history 的有序事件在帧后6拍形成；最终确认前补 LEVELS-2 拍。
        // 保留四个500ps位置，不把辅助事件拉成长脉冲；每相仅查询自身及之前3个位置。
        localparam integer LEVELS = $clog2(CARRY_NUM);
        localparam integer ALIGN_CYCLES = (LEVELS>=2) ? LEVELS-2 : 0;
        wire [3:0] rise_history [0:ALIGN_CYCLES+1];
        wire [3:0] fall_history [0:ALIGN_CYCLES+1];
        assign rise_history[0] = aux_rise_slots;
        assign fall_history[0] = aux_fall_slots;
        genvar delay_stage;
        for (delay_stage=1; delay_stage<=ALIGN_CYCLES+1; delay_stage=delay_stage+1) begin : g_align
            reg [3:0] rise_q, fall_q;
            always @(posedge clk_500m or negedge rst_n_0)
                if (!rst_n_0) begin rise_q <= 0; fall_q <= 0; end
                else begin
                    rise_q <= rise_history[delay_stage-1];
                    fall_q <= fall_history[delay_stage-1];
                end
            assign rise_history[delay_stage] = rise_q;
            assign fall_history[delay_stage] = fall_q;
        end
        wire [3:0] rise_now = rise_history[ALIGN_CYCLES];
        wire [3:0] fall_now = fall_history[ALIGN_CYCLES];
        // 同一边沿可能在相邻两个TDL帧中都有候选。只允许其首次确认帧参与选择，
        // 防止已确认边沿的尾部候选与下一个真实异极性边沿混成冲突帧。
        // 归属位随事件采样帧推进，不使用超时窗口，也不改变原候选的优先级或码值。
        // claimed是当前事件与相位前缀的交集；寄存前缀后再取交集，与原逐位寄存严格同拍。
        wire [3:0] rise_cover =
            ({4{pack0_d1[9:8]==2'b11}} & 4'b1111) |
            ({4{pack270_to90[9:8]==2'b11}} & 4'b0111) |
            ({4{pack180_d1[9:8]==2'b11}} & 4'b0011) |
            ({4{pack90_d2[9:8]==2'b11}} & 4'b0001);
        wire [3:0] fall_cover =
            ({4{pack0_d1[9:8]==2'b10}} & 4'b1111) |
            ({4{pack270_to90[9:8]==2'b10}} & 4'b0111) |
            ({4{pack180_d1[9:8]==2'b10}} & 4'b0011) |
            ({4{pack90_d2[9:8]==2'b10}} & 4'b0001);
        wire [3:0] rise_claimed_now=rise_now & rise_cover;
        wire [3:0] fall_claimed_now=fall_now & fall_cover;
        reg [3:0] rise_cover_previous,fall_cover_previous;
        always @(posedge clk_500m or negedge rst_n_0)
            if(!rst_n_0) begin rise_cover_previous<=0;fall_cover_previous<=0;end
            else begin
                rise_cover_previous<=frame_ready ? rise_cover : 4'b0000;
                fall_cover_previous<=frame_ready ? fall_cover : 4'b0000;
            end
        wire [3:0] rise_claimed_previous=rise_history[ALIGN_CYCLES+1] & rise_cover_previous;
        wire [3:0] fall_claimed_previous=fall_history[ALIGN_CYCLES+1] & fall_cover_previous;
        wire [3:0] rise_previous=rise_history[ALIGN_CYCLES+1] & ~rise_claimed_previous;
        wire [3:0] fall_previous=fall_history[ALIGN_CYCLES+1] & ~fall_claimed_previous;
        function single_event;
            input [3:0] events;
            begin single_event=(|events) && ((events & (events-4'b0001))==0);end
        endfunction
        // 与now同时到达的前缀OR、后缀OR和后缀唯一标志，从既有上一级history计算。
        wire [3:0] rise_prefix_now,fall_prefix_now;
        wire [3:0] rise_suffix_now,fall_suffix_now,rise_single_now,fall_single_now;
        genvar stat;
        for(stat=0;stat<4;stat=stat+1) begin : g_stats
            if(ALIGN_CYCLES>0) begin : g_registered
                reg rp,fp,rs,fs,ru,fu;
                always @(posedge clk_500m or negedge rst_n_0)
                    if(!rst_n_0) begin rp<=0;fp<=0;rs<=0;fs<=0;ru<=0;fu<=0;end
                    else begin
                        rp<=|rise_history[ALIGN_CYCLES-1][stat:0];
                        fp<=|fall_history[ALIGN_CYCLES-1][stat:0];
                        rs<=|rise_history[ALIGN_CYCLES-1][3:stat];
                        fs<=|fall_history[ALIGN_CYCLES-1][3:stat];
                        ru<=single_event(rise_history[ALIGN_CYCLES-1]>>stat);
                        fu<=single_event(fall_history[ALIGN_CYCLES-1]>>stat);
                    end
                assign rise_prefix_now[stat]=rp;assign fall_prefix_now[stat]=fp;
                assign rise_suffix_now[stat]=rs;assign fall_suffix_now[stat]=fs;
                assign rise_single_now[stat]=ru;assign fall_single_now[stat]=fu;
            end else begin : g_no_align
                assign rise_prefix_now[stat]=|rise_now[stat:0];assign fall_prefix_now[stat]=|fall_now[stat:0];
                assign rise_suffix_now[stat]=|rise_now[3:stat];assign fall_suffix_now[stat]=|fall_now[3:stat];
                assign rise_single_now[stat]=single_event(rise_now>>stat);assign fall_single_now[stat]=single_event(fall_now>>stat);
            end
        end
        wire r0=pack0_d1[9:8]==2'b11;
        wire r180=pack180_d1[9:8]==2'b11;
        wire r90=pack90_d2[9:8]==2'b11;
        wire f0=pack0_d1[9:8]==2'b10;
        wire f180=pack180_d1[9:8]==2'b10;
        wire f90=pack90_d2[9:8]==2'b10;
        wire [3:0] rise_remaining_next,fall_remaining_next;
        reg [3:0] rise_remaining_previous,fall_remaining_previous;
        genvar tail;
        for(tail=0;tail<4;tail=tail+1) begin : g_remaining
            localparam integer FROM180=(tail<2)?2:tail;
            localparam integer FROM90=(tail<1)?1:tail;
            wire r_no270=!r0 && (r180 ? rise_suffix_now[FROM180] : r90 ? rise_suffix_now[FROM90] : rise_suffix_now[tail]);
            wire f_no270=!f0 && (f180 ? fall_suffix_now[FROM180] : f90 ? fall_suffix_now[FROM90] : fall_suffix_now[tail]);
            // 晚到270°类型与frame_ready只控制末级选择；ready为0时直接选未扣除的原事件统计。
            LUT6 #(.INIT(64'hcaaacaaaffff0000)) u_r (.I0(r_no270),.I1(!r0 && rise_suffix_now[3]),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(rise_suffix_now[tail]),.I5(frame_ready),.O(rise_remaining_next[tail]));
            LUT6 #(.INIT(64'hacaaacaaffff0000)) u_f (.I0(f_no270),.I1(!f0 && fall_suffix_now[3]),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(fall_suffix_now[tail]),.I5(frame_ready),.O(fall_remaining_next[tail]));
        end
        wire rise_single_no270=!r0 && (r180 ? rise_single_now[2] : r90 ? rise_single_now[1] : rise_single_now[0]);
        wire fall_single_no270=!f0 && (f180 ? fall_single_now[2] : f90 ? fall_single_now[1] : fall_single_now[0]);
        wire rise_single_next,fall_single_next;
        reg rise_previous_single_q,fall_previous_single_q;
        LUT6 #(.INIT(64'hcaaacaaaffff0000)) u_single_r (.I0(rise_single_no270),.I1(!r0 && rise_single_now[3]),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(rise_single_now[0]),.I5(frame_ready),.O(rise_single_next));
        LUT6 #(.INIT(64'hacaaacaaffff0000)) u_single_f (.I0(fall_single_no270),.I1(!f0 && fall_single_now[3]),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(fall_single_now[0]),.I5(frame_ready),.O(fall_single_next));
        always @(posedge clk_500m or negedge rst_n_0)
            if(!rst_n_0) begin
                rise_remaining_previous<=0;fall_remaining_previous<=0;
                rise_previous_single_q<=0;fall_previous_single_q<=0;
            end else begin
                rise_remaining_previous<=rise_remaining_next;fall_remaining_previous<=fall_remaining_next;
                rise_previous_single_q<=rise_single_next;fall_previous_single_q<=fall_single_next;
            end
        // next前缀与remaining_next属于同一输出帧；在原history边界同时寄存，不新增输出拍数。
        wire [3:0] rise_base_next,fall_base_next;
        reg [3:0] rise_base_q,fall_base_q;
        genvar match_phase;
        for(match_phase=0;match_phase<4;match_phase=match_phase+1) begin : g_base_precompute
            wire next_rise_prefix,next_fall_prefix;
            if(ALIGN_CYCLES>0) begin : g_from_history
                assign next_rise_prefix=|rise_history[ALIGN_CYCLES-1][match_phase:0];
                assign next_fall_prefix=|fall_history[ALIGN_CYCLES-1][match_phase:0];
            end else begin : g_from_input
                wire [3:0] next_rise_slots=(armed && ordered_ready) ? (ordered_samples & ~previous_slots) : 4'b0000;
                wire [3:0] next_fall_slots=(armed && ordered_ready) ? (~ordered_samples & previous_slots) : 4'b0000;
                assign next_rise_prefix=|next_rise_slots[match_phase:0];
                assign next_fall_prefix=|next_fall_slots[match_phase:0];
            end
            if(match_phase==3) begin : g_last_phase
                assign rise_base_next[match_phase]=next_rise_prefix;
                assign fall_base_next[match_phase]=next_fall_prefix;
            end else begin : g_with_previous
                localparam integer FROM=match_phase+1;
                localparam integer FROM180=(FROM<2)?2:FROM;
                localparam integer FROM90=(FROM<1)?1:FROM;
                wire r_none=!r0 && (r180 ? rise_suffix_now[FROM180] : r90 ? rise_suffix_now[FROM90] : rise_suffix_now[FROM]);
                wire f_none=!f0 && (f180 ? fall_suffix_now[FROM180] : f90 ? fall_suffix_now[FROM90] : fall_suffix_now[FROM]);
                LUT6 #(.INIT(64'hcaaacaaaffff0000)) u_r (.I0(next_rise_prefix | r_none),.I1(next_rise_prefix | (!r0 && rise_suffix_now[3])),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(next_rise_prefix | rise_suffix_now[FROM]),.I5(frame_ready),.O(rise_base_next[match_phase]));
                LUT6 #(.INIT(64'hacaaacaaffff0000)) u_f (.I0(next_fall_prefix | f_none),.I1(next_fall_prefix | (!f0 && fall_suffix_now[3])),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4(next_fall_prefix | fall_suffix_now[FROM]),.I5(frame_ready),.O(fall_base_next[match_phase]));
            end
        end
        always @(posedge clk_500m or negedge rst_n_0)
            if(!rst_n_0) begin rise_base_q<=0;fall_base_q<=0;end
            else begin rise_base_q<=rise_base_next;fall_base_q<=fall_base_next;end
        wire [3:0] base_rise_match, base_fall_match;
        assign base_rise_match[0] = rise_base_q[0];
        assign base_rise_match[1] = rise_base_q[1];
        assign base_rise_match[2] = rise_base_q[2];
        assign base_rise_match[3] = rise_base_q[3];
        assign base_fall_match[0] = fall_base_q[0];
        assign base_fall_match[1] = fall_base_q[1];
        assign base_fall_match[2] = fall_base_q[2];
        assign base_fall_match[3] = fall_base_q[3];

        // 保持原确认优先；仅在整帧无原有效候选时考虑前帧回退。
        wire base_confirmed =
            (pack0_d1[9] && (pack0_d1[8] ? base_rise_match[3] : base_fall_match[3])) ||
            (pack270_to90[9] && (pack270_to90[8] ? base_rise_match[2] : base_fall_match[2])) ||
            (pack180_d1[9] && (pack180_d1[8] ? base_rise_match[1] : base_fall_match[1])) ||
            (pack90_d2[9] && (pack90_d2[8] ? base_rise_match[0] : base_fall_match[0]));
        wire raw_has_rise = pack0_d1[9:8]==2'b11 || pack270_to90[9:8]==2'b11 ||
                            pack180_d1[9:8]==2'b11 || pack90_d2[9:8]==2'b11;
        wire raw_has_fall = pack0_d1[9:8]==2'b10 || pack270_to90[9:8]==2'b10 ||
                            pack180_d1[9:8]==2'b10 || pack90_d2[9:8]==2'b10;
        // 多事件或混合极性时不推测归属；previous已按原claimed规则扣除使用过的事件。
        wire rise_previous_single = rise_previous_single_q;
        wire fall_previous_single = fall_previous_single_q;
        wire rise_fallback = !base_confirmed && raw_has_rise && !raw_has_fall && rise_previous_single;
        wire fall_fallback = !base_confirmed && raw_has_fall && !raw_has_rise && fall_previous_single;
        assign aux_rise_match = base_rise_match | {4{rise_fallback}};
        assign aux_fall_match = base_fall_match | {4{fall_fallback}};
        // 270°包在90°时钟产生，到下一0°仅1.5ns；提前计算三个余因子，避免晚到信号穿过全局归约。
        // 与上方E规则完全等价，末级LUT5只选择对应候选类型；没有增加寄存器或跨域采样。
        function [7:0] guarded_types;
            input [7:0] types;
            input [3:0] base_r,base_f;
            input single_r,single_f;
            reg confirmed,has_r,has_f,back_r,back_f;
            integer q;
            begin
                confirmed=0;has_r=0;has_f=0;
                for(q=0;q<4;q=q+1) begin
                    has_r=has_r || types[2*q+:2]==2'b11;
                    has_f=has_f || types[2*q+:2]==2'b10;
                    confirmed=confirmed || (types[2*q+:2]==2'b11 && base_r[q]) ||
                                           (types[2*q+:2]==2'b10 && base_f[q]);
                end
                back_r=!confirmed && !has_f && single_r;
                back_f=!confirmed && !has_r && single_f;
                for(q=0;q<4;q=q+1)
                    guarded_types[2*q+:2]=confirm_edge(types[2*q+:2],base_r[q] | back_r,base_f[q] | back_f);
            end
        endfunction
        wire [7:0] if_invalid=guarded_types({pack0_d1[9:8],2'b00,pack180_d1[9:8],pack90_d2[9:8]},base_rise_match,base_fall_match,rise_previous_single,fall_previous_single);
        wire [7:0] if_fall=guarded_types({pack0_d1[9:8],2'b10,pack180_d1[9:8],pack90_d2[9:8]},base_rise_match,base_fall_match,rise_previous_single,fall_previous_single);
        wire [7:0] if_rise=guarded_types({pack0_d1[9:8],2'b11,pack180_d1[9:8],pack90_d2[9:8]},base_rise_match,base_fall_match,rise_previous_single,fall_previous_single);
        genvar bit_id;
        for(bit_id=0;bit_id<8;bit_id=bit_id+1) begin : g_guard_mux
            LUT5 #(.INIT(32'hf0ccaaaa)) u_mux (
                .I0(if_invalid[bit_id]),.I1(if_fall[bit_id]),.I2(if_rise[bit_id]),
                .I3(pack270_to90[8]),.I4(pack270_to90[9]),.O(guarded_final_types[bit_id]));
            // 将原末级frame_ready门控并入选择LUT，输出寄存器及拍数不变。
            LUT6 #(.INIT(64'hf0ccaaaa00000000)) u_output (
                .I0(if_invalid[bit_id]),.I1(if_fall[bit_id]),.I2(if_rise[bit_id]),
                .I3(pack270_to90[8]),.I4(pack270_to90[9]),.I5(frame_ready),.O(guarded_output_types[bit_id]));
        end

`ifndef SYNTHESIS
        initial if (CARRY_NUM<4) $fatal(1,"四相辅助通路要求CARRY_NUM>=4");
`endif
    end endgenerate
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

    wire [1:0] final_type0   = ENABLE_AUX_4PHASE ? guarded_final_types[6+:2] : confirm_edge(pack0_d1[9:8],        aux_rise_match[3], aux_fall_match[3]);
    wire [1:0] final_type90  = ENABLE_AUX_4PHASE ? guarded_final_types[0+:2] : confirm_edge(pack90_d2[9:8],       aux_rise_match[0], aux_fall_match[0]);
    wire [1:0] final_type180 = ENABLE_AUX_4PHASE ? guarded_final_types[2+:2] : confirm_edge(pack180_d1[9:8],      aux_rise_match[1], aux_fall_match[1]);
    wire [1:0] final_type270 = ENABLE_AUX_4PHASE ? guarded_final_types[4+:2] : confirm_edge(pack270_to90[9:8],    aux_rise_match[2], aux_fall_match[2]);

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
            sync_edge_polarity <= ENABLE_AUX_4PHASE ? guarded_output_types :
                (frame_ready ? {final_type0,final_type270,final_type180,final_type90} : 8'd0);
            sync_edge_valid <= ENABLE_AUX_4PHASE ?
                {guarded_output_types[7],guarded_output_types[5],guarded_output_types[3],guarded_output_types[1]} :
                (frame_ready ? {final_type0[1],final_type270[1],final_type180[1],final_type90[1]} : 4'd0);
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

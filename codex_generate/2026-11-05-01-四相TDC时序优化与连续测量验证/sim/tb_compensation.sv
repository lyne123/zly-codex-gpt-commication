`timescale 1ps/1ps
// 覆盖显式旁路、正负偏移、8路映射、连续valid、冲突抑制与多次粗计数回卷。
module check_locate #(parameter CW=10)(output reg done=0);
    localparam M=2000*(1<<CW);
    reg clk=0,rst_n=0,valid=0,polarity=0,conflict=0,repeat_error=0;
    reg [7:0] code=0;
    reg [1:0] index=0;
    always #1000 clk=~clk;
    wire ov,ot,bv,bt,cv,ct,zv,zt;
    wire [CW+10:0] ots,bts,cts,zts;
    // 小模数验证跨周期修正，大模数验证18位signed极值。
    localparam signed [17:0] R0=(CW==10)?18'sd131071:18'sd2500;
    localparam signed [17:0] R90=(CW==10)?-18'sd131072:-18'sd2500;
    localparam signed [17:0] R180=18'sd0, R270=18'sd1999;
    localparam signed [17:0] F0=-18'sd1999, F90=18'sd5000;
    localparam signed [17:0] F180=-18'sd5000, F270=18'sd1;
    tdc_time_locate_original #(.COARSE_W(CW)) original(
        .clk_500m(clk),.rst_n(rst_n),.edge_valid(valid),.edge_type_q(polarity),
        .chosen_code(code),.sel_index(index),.polarity_conflict(conflict),.repeat_error(repeat_error),
        .timestamp_valid(ov),.timestamp_edge_type(ot),.timestamp_ps(ots));
    tdc_time_locate #(.COARSE_W(CW),.ENABLE_SKEW_COMP(0),
        .RISE_OFFSET_0_PS(R0),.RISE_OFFSET_90_PS(R90),.RISE_OFFSET_180_PS(R180),.RISE_OFFSET_270_PS(R270),
        .FALL_OFFSET_0_PS(F0),.FALL_OFFSET_90_PS(F90),.FALL_OFFSET_180_PS(F180),.FALL_OFFSET_270_PS(F270)) bypass(
        .clk_500m(clk),.rst_n(rst_n),.edge_valid(valid),.edge_type_q(polarity),
        .chosen_code(code),.sel_index(index),.polarity_conflict(conflict),.repeat_error(repeat_error),
        .timestamp_valid(bv),.timestamp_edge_type(bt),.timestamp_ps(bts));
    tdc_time_locate #(.COARSE_W(CW),.ENABLE_SKEW_COMP(1),
        .RISE_OFFSET_0_PS(R0),.RISE_OFFSET_90_PS(R90),.RISE_OFFSET_180_PS(R180),.RISE_OFFSET_270_PS(R270),
        .FALL_OFFSET_0_PS(F0),.FALL_OFFSET_90_PS(F90),.FALL_OFFSET_180_PS(F180),.FALL_OFFSET_270_PS(F270)) corrected(
        .clk_500m(clk),.rst_n(rst_n),.edge_valid(valid),.edge_type_q(polarity),
        .chosen_code(code),.sel_index(index),.polarity_conflict(conflict),.repeat_error(repeat_error),
        .timestamp_valid(cv),.timestamp_edge_type(ct),.timestamp_ps(cts));
    tdc_time_locate #(.COARSE_W(CW),.ENABLE_SKEW_COMP(1)) zero_enabled(
        .clk_500m(clk),.rst_n(rst_n),.edge_valid(valid),.edge_type_q(polarity),
        .chosen_code(code),.sel_index(index),.polarity_conflict(conflict),.repeat_error(repeat_error),
        .timestamp_valid(zv),.timestamp_edge_type(zt),.timestamp_ps(zts));
    integer offsets[0:4];
    integer j,expected,seen=0,cycles=0,offset_now;
    always @(posedge clk) begin
        if (!rst_n) begin
            for(j=0;j<5;j=j+1) offsets[j]=0;
        end else begin
            case(index)
                0: offset_now=polarity?R90:F90;
                1: offset_now=polarity?R180:F180;
                2: offset_now=polarity?R270:F270;
                3: offset_now=polarity?R0:F0;
            endcase
            for(j=4;j>0;j=j-1) offsets[j]=offsets[j-1];
            offsets[0]=offset_now;
        end
        #1;
        if ({bv,bt,bts} !== {ov,ot,ots}) $fatal(1,"Bypass mismatch CW=%0d",CW);
        if ({zv,zt,zts} !== {ov,ot,ots}) $fatal(1,"Enabled-zero mismatch CW=%0d",CW);
        if ({cv,ct} !== {ov,ot}) $fatal(1,"Control latency mismatch CW=%0d",CW);
        if (ov) begin
            expected=($signed({1'b0,ots})-offsets[4])%M;
            if(expected<0) expected=expected+M;
            if(cts !== expected[CW+10:0])
                $fatal(1,"Correction mismatch CW=%0d raw=%0d offset=%0d actual=%0d expected=%0d",CW,ots,offsets[4],cts,expected);
            seen=seen+1;
        end
    end
    integer k;
    initial begin
        #3000;
        @(negedge clk) rst_n=1;
        for(k=0;k<6000;k=k+1) begin
            @(negedge clk);
            valid=(k%11!=0);
            polarity=(k/4)%2;
            index=k%4;
            code=k%66;
            conflict=(k%17==0);
            repeat_error=(k%13==0);
            if(k==3100) rst_n=0;
            if(k==3102) rst_n=1;
        end
        @(negedge clk) valid=0;
        repeat(8) @(negedge clk);
        if(seen<4000) $fatal(1,"Insufficient valid checks");
        $display("COMPENSATION_PASS CW=%0d checks=%0d",CW,seen);
        done=1;
    end
endmodule
module tb_compensation;
    wire a,b;
    check_locate #(.CW(2)) small_wrap(a);
    check_locate #(.CW(10)) full_width(b);
    initial begin wait(a&&b); $display("ALL_COMPENSATION_TESTS_PASS"); $finish; end
endmodule

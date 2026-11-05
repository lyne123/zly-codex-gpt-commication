`timescale 1ps/1ps
// 用完整冻结激励逐拍证明四相整包及有效窗口只共同延迟一拍。
module tb_front_alignment;
    reg sys_clk=0,rst=1,pwm=0;
    always #5000 sys_clk=~sys_clk;
    wire c0,c90,c180,c270,c100,locked;
    clk_wiz_0 clocks(.clk_in1(sys_clk),.reset(rst),.locked(locked),.clk_out1(c0),.clk_out2(c90),.clk_out3(c180),.clk_out4(c270),.clk_out5(c100));
    wire reset_n=!rst&&locked;
    wire [31:0] old_codes,new_codes;
    wire [3:0] old_mask,new_mask;
    wire [7:0] old_types,new_types;
    wire old_ready,new_ready;
    tdc_fine_layer_original old_dut(c0,c90,c180,c270,reset_n,pwm,old_codes,old_mask,old_types,old_ready);
    tdc_fine_layer new_dut(c0,c90,c180,c270,reset_n,pwm,new_codes,new_mask,new_types,new_ready);
    reg prev_ready=0;
    reg [31:0] prev_codes;
    reg [3:0] prev_mask;
    reg [7:0] prev_types;
    integer checks=0,valid_frames=0;
    always @(negedge c0) begin
        if (!reset_n) prev_ready=0;
        else begin
            if (new_ready!==prev_ready) $fatal(1,"ready延迟不匹配 time=%0t",$time);
            if (prev_ready) begin
                if ({new_codes,new_mask,new_types}!=={prev_codes,prev_mask,prev_types})
                    $fatal(1,"四相码/极性/valid错位 time=%0t",$time);
                checks=checks+1;
                if (|new_mask) valid_frames=valid_frames+1;
            end
            prev_ready=old_ready;prev_codes=old_codes;prev_mask=old_mask;prev_types=old_types;
        end
    end
    integer f,rc,id;
    time rise_ps,fall_ps,period_ps;
    initial begin
        #200000 rst=0;
        f=$fopen("U:/sim/stimuli/validation.txt","r");
        if (!f) $fatal(1,"激励不存在");
        while (!$feof(f)) begin
            rc=$fscanf(f,"%d %d %d %d\n",id,rise_ps,fall_ps,period_ps);
            if (rc==4) begin #(rise_ps-$time) pwm=1;#(fall_ps-$time) pwm=0;end
            else if (!$feof(f)) $fatal(1,"激励格式错误");
        end
        #500000;
        if (valid_frames<7024) $fatal(1,"有效帧数不足");
        $display("FRONT_ALIGNMENT_PASS checks=%0d valid_frames=%0d added_cycles=1",checks,valid_frames);
        $finish;
    end
endmodule

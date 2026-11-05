`timescale 1ps/1ps
// 检查PWM已为高电平时释放复位不会生成虚假辅助事件。
module tb_aux_reset;
    reg c0=0,c90=0,c180=0,c270=0,rst_n=0,pwm=1;
    always #1000 c0=~c0;
    initial begin #500; forever #1000 c90=~c90; end
    initial begin #1000; forever #1000 c180=~c180; end
    initial begin #1500; forever #1000 c270=~c270; end
    tdc_fine_layer dut(.clk_500m(c0),.clk_500m_deg90(c90),.clk_500m_deg180(c180),.clk_500m_deg270(c270),.rst_n(rst_n),.pwm_in(pwm),.all_fine_code(),.sync_edge_valid(),.sync_edge_polarity(),.sync_valid());
    integer rises=0,falls=0,fd;
    function integer ones(input [3:0] value);
        integer i;
        begin ones=0; for(i=0;i<4;i=i+1) ones=ones+value[i]; end
    endfunction
    always @(negedge c0) begin
        rises=rises+ones(dut.g_aux_4phase.aux_rise_slots);
        falls=falls+ones(dut.g_aux_4phase.aux_fall_slots);
        if(fd && (|dut.g_aux_4phase.aux_rise_slots || |dut.g_aux_4phase.aux_fall_slots))
            $fdisplay(fd,"%0t,%0d,%0d",$time,dut.g_aux_4phase.aux_rise_slots,dut.g_aux_4phase.aux_fall_slots);
    end
    initial begin
        fd=$fopen("W:/results/AUX_RESET_EVENTS.csv","w");
        $fdisplay(fd,"time_ps,rise_slots,fall_slots");
        #20000 rst_n=1;
        #100000;
        if(rises!=0 || falls!=0) $fatal(1,"高电平复位释放生成虚假事件");
        pwm=0; #5000 pwm=1; #50000;
        if(rises!=1 || falls!=1) $fatal(1,"第一组真实边沿计数错误");
        rst_n=0; #20000 rst_n=1; #100000;
        if(rises!=1 || falls!=1) $fatal(1,"再次复位生成虚假事件");
        pwm=0; #3000 pwm=1; #50000;
        if(rises!=2 || falls!=2) $fatal(1,"第二组真实边沿计数错误");
        $fclose(fd);$display("AUX_RESET_PASS rises=%0d falls=%0d",rises,falls);$finish;
    end
endmodule

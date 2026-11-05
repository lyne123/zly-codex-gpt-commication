`timescale 1ps/1ps
// 补充因果实验：把真实SDF四相输出逐周期送入未修改的候选器，不代替主激励仿真。
module tb_candidate_replay;
    reg clk=0,rst_n=0,ready=0;
    always #1000 clk=~clk;
    reg [31:0] codes=0;
    reg [3:0] mask=0;
    reg [7:0] types=0;
    wire valid,polarity,conflict,repeat_error;
    wire [7:0] code;
    wire [1:0] index;
    tdc_time_candicate dut(clk,rst_n,ready,codes,mask,types,valid,polarity,code,index,conflict,repeat_error);
    integer input_fd,out_fd,trace_fd,rc,dummy_coarse;
    reg [31:0] next_codes;
    reg [3:0] next_mask;
    reg [7:0] next_types;
    time next_time,origin_time,logical_time;
    reg [4095:0] header;
    integer cycle=0,emitted=0,conflicts=0;
    task read_next;
        begin rc=$fscanf(input_fd,"%d,%d,%d,%d,%d\n",next_time,dummy_coarse,next_mask,next_types,next_codes);end
    endtask
    initial begin
        input_fd=$fopen("T:/results/baseline/gate_validation/raw.csv","r");
        out_fd=$fopen("U:/results/candidate_replay.csv","w");
        trace_fd=$fopen("U:/results/candidate_replay_pipeline.csv","w");
        $fdisplay(out_fd,"time_ps,valid,type,index,code,conflict,repeat_error");
        $fdisplay(trace_fd,"time_ps,input_mask,input_types,s1_mask,s2_mask,s2_conflict,s3_valid,s3_conflict,s4_valid,s4_conflict,edge_valid,polarity_conflict,repeat_error");
        rc=$fgets(header,input_fd);read_next;origin_time=next_time;
        repeat(4) @(negedge clk);
        rst_n=1;ready=1;
        while (rc==5 || cycle<140000) begin
            @(negedge clk);
            logical_time=origin_time+cycle*2000;
            codes=0;mask=0;types=0;
            if (rc==5 && next_time==logical_time) begin
                codes=next_codes;mask=next_mask;types=next_types;read_next;
            end
            if (rc==5 && next_time<logical_time) $fatal(1,"源时间不是2000ps整周期");
            @(posedge clk);#1;
            if (valid||conflict||repeat_error) begin
                $fdisplay(out_fd,"%0d,%0d,%0d,%0d,%0d,%0d,%0d",logical_time+2000,valid,polarity,index,code,conflict,repeat_error);
                if(valid) emitted=emitted+1;
                if(conflict) conflicts=conflicts+1;
            end
            if ((logical_time>=238600000&&logical_time<=238900000)||(logical_time>=241900000&&logical_time<=242200000)||(logical_time>=245200000&&logical_time<=245500000))
                $fdisplay(trace_fd,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",logical_time+2000,mask,types,dut.s1_mask,dut.s2_mask,dut.s2_conflict,dut.s3_valid,dut.s3_conflict,dut.s4_valid,dut.s4_conflict,valid,conflict,repeat_error);
            cycle=cycle+1;
        end
        $display("CANDIDATE_REPLAY_DONE emitted=%0d conflicts=%0d",emitted,conflicts);
        $fclose(input_fd);$fclose(out_fd);$fclose(trace_fd);$finish;
    end
endmodule

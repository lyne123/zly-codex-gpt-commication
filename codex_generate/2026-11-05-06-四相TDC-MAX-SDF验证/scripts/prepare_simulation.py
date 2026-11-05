"""只适配测试平台层级观察，使用冻结激励和外部单次MAX-SDF注释。"""
from pathlib import Path
import hashlib,json,re,shutil
ROOT=Path('Z:/');SOURCE=Path('W:/');AUX=Path('X:/')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    net=ROOT/'netlist/post_route_timing.v';sdf=ROOT/'netlist/post_route_max.sdf'
    assert '$sdf_annotate' not in net.read_text(encoding='utf-8'),'网表包含内部SDF注释，不能叠加外部注释'
    manifest=json.loads((ROOT/'inputs/SOURCE_MANIFEST.json').read_text());assert sha(SOURCE/'results/compensated/design.dcp')==manifest['files']['results/compensated/design.dcp']['sha256']
    text=(AUX/'sim/tb_gate.sv').read_text(encoding='utf-8')
    # 原始复位/激励及测量观察不改；追加只读的FIFO计数和同拍复位观察。
    assert '`ifdef GATE_SDF' in text
    text=text.replace('\nendmodule','\n`include "fifo_reset_observer.svh"\nendmodule')
    (ROOT/'sim/tb_tdc_sdf.sv').write_text(text,encoding='utf-8')
    shutil.copyfile(AUX/'sim/gate_observer.svh',ROOT/'sim/gate_observer.svh')
    (ROOT/'sim/fifo_reset_observer.svh').write_text('''// 仅测试平台观察，不改FIFO复位或写入逻辑。
integer fifo_write_fd,fifo_read_fd,reset_fd,orig_cycles=0,replica_cycles=0;
initial begin #1;
  fifo_write_fd=$fopen({output_dir,"/FIFO_WRITES.csv"},"w");
  fifo_read_fd=$fopen({output_dir,"/FIFO_READS.csv"},"w");
  reset_fd=$fopen({output_dir,"/RESET_TRACE.csv"},"w");
  $fdisplay(fifo_write_fd,"time_ps,kind,data,full,busy,measurement_valid");
  $fdisplay(fifo_read_fd,"time_ps,kind,data,empty,busy,output_valid");
  $fdisplay(reset_fd,"time_ps,signal,value,own_clock_cycles,original_Q,replica_Q,MMCM_locked");
end
always @(posedge dut.clk_500m) begin
  if(fifo_write_fd && dut.result_fifo_wr_en)
    $fdisplay(fifo_write_fd,"%0t,result,%0d,%0d,%0d,%0d",$time,dut.pulse_width_ps,dut.result_fifo_full,dut.result_fifo_wr_rst_busy,dut.pulse_width_valid);
  if(fifo_write_fd && dut.error_fifo_wr_en)
    $fdisplay(fifo_write_fd,"%0t,error,%0d,%0d,%0d,%0d",$time,dut.error_event_code,dut.error_fifo_full,dut.error_fifo_wr_rst_busy,dut.error_event_valid);
end
always @(posedge dut.clk_100m) begin
  if(fifo_read_fd && dut.result_fifo_rd_en)
    $fdisplay(fifo_read_fd,"%0t,result,%0d,%0d,%0d,%0d",$time,dut.pulse_width_ps_100m,dut.result_fifo_empty,dut.result_fifo_rd_rst_busy,dut.pulse_width_valid_100m);
  if(fifo_read_fd && dut.error_fifo_rd_en)
    $fdisplay(fifo_read_fd,"%0t,error,%0d,%0d,%0d,%0d",$time,dut.error_code_100m,dut.error_fifo_empty,dut.error_fifo_rd_rst_busy,dut.error_valid_100m);
end
always @(posedge dut.\\rst_sync_500m_reg[1] .C_dly) orig_cycles=orig_cycles+1;
always @(posedge dut.rst_result_fifo_500m_reg.C_dly) replica_cycles=replica_cycles+1;
always @(dut.rst_sync_500m[1]) if(reset_fd)
  $fstrobe(reset_fd,"%0t,original,%0d,%0d,%0d,%0d,%0d",$time,dut.rst_sync_500m[1],orig_cycles,dut.rst_sync_500m[1],dut.rst_result_fifo_500m,dut.mmcm_locked);
always @(dut.rst_result_fifo_500m) if(reset_fd)
  $fstrobe(reset_fd,"%0t,replica,%0d,%0d,%0d,%0d,%0d",$time,dut.rst_result_fifo_500m,replica_cycles,dut.rst_sync_500m[1],dut.rst_result_fifo_500m,dut.mmcm_locked);
''',encoding='utf-8')
    work=ROOT/'build/modelsim'
    compile_files=[net,Path('F:/Xilinx/Vivado/2022.2/data/verilog/src/glbl.v'),ROOT/'sim/tb_tdc_sdf.sv']
    (work/'design_files.f').write_text(''.join('"'+str(p).replace('\\','/')+'"\n' for p in compile_files),encoding='ascii')
    # 缺少对象全部报告，禁止消息限额掩盖未匹配路径；时序检查保持默认启用。
    command=['F:/Program Files/modeltech64_2020.4/win64/vsim.exe','-c','-t','1ps','-modelsimini','Z:/build/modelsim/modelsim.ini','-L','simprims_ver','-voptargs=+acc','+transport_int_delays','+transport_path_delays','+pulse_int_r/0','+pulse_int_e/0','+pulse_r/0','+pulse_e/0','-msglimit','none','+sdf_verbose','-sdfannotatepercentage','-sdfmaxerrors','1000000','-sdfmax','/tb_tdc/dut=Z:/netlist/post_route_max.sdf','work.tb_tdc','work.glbl']
    (ROOT/'inputs/SIMULATION_COMMAND.json').write_text(json.dumps(command,indent=2),encoding='utf-8')
    (ROOT/'inputs/EXPORTED_FILES.json').write_text(json.dumps(dict(source_DCP_sha256=sha(SOURCE/'results/compensated/design.dcp'),netlist_sha256=sha(net),SDF_sha256=sha(sdf),netlist_internal_sdf_annotations=0,external_annotation='/tb_tdc/dut with -sdfmax; sole annotation',timescale='1ps',process_corner='slow',source_files_unchanged=True),indent=2),encoding='utf-8')
    (ROOT/'sim/simulation.do').write_text('# 完整运行冻结3512激励；时序违例照常记录，不关闭检查。\nrun -all\nquit -f\n',encoding='utf-8')
    print('SIMULATION_PREPARED; external MAX-SDF only; original stimulus unchanged')
if __name__=='__main__':main()

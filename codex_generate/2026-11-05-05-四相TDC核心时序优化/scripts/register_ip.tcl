# 通过正式工程导入IP，重定位其生成目录；不综合、不实现、不改原IP。
set_param general.maxThreads 1
set root W:/
create_project aux_compensated $root/build/registered -part xc7k325tffg900-2
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
config_ip_cache -use_cache_location $root/build/ip_cache
foreach ip {clk_wiz_0 fifo_tdc_result ila_2 ila_3} {
    import_ip -files $root/inputs/ip/$ip/$ip.xci
}
generate_target all [get_ips]
set fd [open $root/logs/REGISTERED_IP_FILES.txt w]
foreach ip [get_ips] {
    puts $fd "[get_property NAME $ip]\t[get_property IP_FILE $ip]"
    foreach f [get_files -all -of_objects $ip] {puts $fd "  $f"}
}
close $fd
close_project
puts "REGISTER_IP_COMPLETE"

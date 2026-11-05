# 用官方IP缓存接口复用配置完全相同的已综合IP，不伪造run完成状态。
set_param general.maxThreads 1
set root U:/
open_project $root/build/baseline/timing_baseline.xpr
config_ip_cache -use_cache_location $root/build/shared_ip_cache
set_property IP_CACHE_PERMISSIONS {read write} [current_project]
config_ip_cache -import_from_project
foreach ip [get_ips] {puts "BASELINE_IP_CACHE $ip [config_ip_cache -get_id $ip] [config_ip_cache -cache_has_match $ip]"}
close_project
open_project $root/build/compensated/timing_compensated.xpr
config_ip_cache -use_cache_location $root/build/shared_ip_cache
set_property IP_CACHE_PERMISSIONS {read write} [current_project]
foreach ip [get_ips] {puts "COMPENSATED_IP_CACHE_BEFORE $ip [config_ip_cache -get_id $ip] [config_ip_cache -cache_has_match $ip]"}
generate_target all [get_ips] -force
foreach ip [get_ips] {puts "COMPENSATED_IP_CACHE_AFTER $ip used=[config_ip_cache -cache_was_used $ip] match=[config_ip_cache -cache_has_match $ip]"}
close_project

# synth_ip负责实际应用匹配的OOC缓存，generate_target本身只生成源产品。
set_param general.maxThreads 1
set root U:/
puts [help synth_ip]
open_project $root/build/compensated/timing_compensated.xpr
config_ip_cache -use_cache_location $root/build/shared_ip_cache
foreach ip [get_ips] {
    set match [config_ip_cache -cache_has_match $ip]
    if {$match eq ""} {error "没有配置匹配的IP缓存：$ip"}
    puts "APPLY_MATCHED_IP_CACHE $ip $match"
    synth_ip $ip
    puts "APPLIED_IP_CACHE $ip used=[config_ip_cache -cache_was_used $ip]"
}
close_project

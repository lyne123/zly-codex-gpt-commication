# 本轮仅使用已保留的AD23生产BIT，不使用时序未通过的Debug实现。
# 100MHz错误FIFO触发只证明错误事件存在，不能替代500MHz前端内部信号定位。
set work [file dirname [file normalize [info script]]]
set attempt [expr {[llength $argv]>0 ? [lindex $argv 0] : "board_attempt_01"}]
set cs_url [expr {[llength $argv]>1 ? [lindex $argv 1] : "TCP:127.0.0.1:3046"}]
set program_hz [expr {[llength $argv]>2 ? [lindex $argv 2] : 3000000}]
set hw_url [expr {[llength $argv]>3 ? [lindex $argv 3] : "localhost:3121"}]
set out $work/$attempt
if {[file exists $out]} {error "已有本次硬件尝试，禁止覆盖原始记录"}
file mkdir $out
set fd [open $out/HARDWARE_STATUS.txt w]
fconfigure $fd -encoding utf-8
set opened 0
proc dump_config_status {device output} {
    # 只读配置状态/启动控制，不读取密钥、eFUSE或其他安全信息。
    catch {refresh_hw_device -update_hw_probes false $device}
    set f [open $output w]
    foreach property [lsort [list_property $device]] {
        if {[string match REGISTER.CONFIG_STATUS* $property] || [string match REGISTER.BOOT_STATUS* $property] || [string match REGISTER.COR0* $property] || [string match REGISTER.COR1* $property] || $property eq "PART" || $property eq "PROGRAM.IS_PROGRAMMED"} {
            if {![catch {get_property $property $device} value]} {puts $f "$property=$value"}
        }
    }
    close $f
}
set rc [catch {
    open_hw_manager
    connect_hw_server -url $hw_url -cs_url $cs_url
    set targets [get_hw_targets -quiet]
    puts $fd "targets=$targets"
    # 复用最近一次10082个有效输出日志确认的C306线缆，不根据旧截图选择另一目标。
    set known [get_hw_targets -quiet -filter {NAME =~ *C3067D03ABCD*}]
    if {[llength $known]==1} {
        set target [lindex $known 0]
    } else {error "没有唯一的既有C306目标，禁止擅自烧录其他板卡"}
    puts $fd "selected_target=$target"
    set_property PARAM.FREQUENCY $program_hz $target
    open_hw_target $target
    set opened 1
    set dev [get_hw_devices -quiet -filter {PART =~ xc7k325t*}]
    if {[llength $dev]!=1} {error "未找到唯一XC7K325T"}
    current_hw_device $dev
    puts $fd "part=[get_property PART $dev]\nJTAG_connected=1"
    puts "BOARD_CONNECTED device=$dev"
    flush stdout
    dump_config_status $dev $out/CONFIG_BEFORE.txt
    set_property PROGRAM.FILE $work/PRODUCTION_AD23.bit $dev
    set_property PROBES.FILE $work/PRODUCTION_AD23.ltx $dev
    set_property FULL_PROBES.FILE $work/PRODUCTION_AD23.ltx $dev
    puts $fd "program_JTAG_Hz=$program_hz"
    flush $fd
    set program_rc [catch {program_hw_devices $dev} program_reason]
    dump_config_status $dev $out/CONFIG_AFTER.txt
    if {$program_rc} {error $program_reason}
    puts $fd "production_programmed=1\nprogramming=volatile_FPGA_RAM\nflash_programmed=0\nfailed_Debug_implementation_used=0"
    flush $fd
    puts "PRODUCTION_AD23_PROGRAMMED"
    flush stdout
    set_property PARAM.FREQUENCY 1000000 $target
    after 2000
    refresh_hw_device $dev
    set all_ilas [get_hw_ilas -of_objects $dev]
    foreach i $all_ilas {puts $fd "ILA=[get_property CELL_NAME $i]; UUID=[get_property CORE_UUID $i]"}
    set ila [get_hw_ilas -of_objects $dev -filter {CELL_NAME == u_ila3}]
    if {[llength $ila]!=1 || [string toupper [get_property CORE_UUID $ila]] ne "005AAA8F6BEB5365914C104C10152EC8"} {error "生产版100MHz ILA签名不匹配"}
    foreach probe [get_hw_probes -of_objects $ila] {
        set width [get_property WIDTH $probe]
        set_property DISPLAY_RADIX UNSIGNED $probe
        set_property TRIGGER_COMPARE_VALUE "eq${width}'b[string repeat X $width]" $probe
    }
    set_property CONTROL.WINDOW_COUNT 1 $ila
    set_property CONTROL.DATA_DEPTH 2048 $ila
    set_property CONTROL.TRIGGER_POSITION 1536 $ila
    set_property CONTROL.TRIGGER_CONDITION AND $ila
    set activity 0
    for {set n 1} {$n<=3} {incr n} {
        run_hw_ila -trigger_now $ila
        # timeout单位分钟，0.1分钟为6秒。
        wait_on_hw_ila -timeout 0.1 $ila
        set data [upload_hw_ila_data $ila]
        set file $out/[format "ACTIVITY_%02d.csv" $n]
        write_hw_ila_data -csv_file $file $data
        set stream [open $file r];set lines [split [string trim [read $stream]] \n];close $stream
        set columns [split [string trim [lindex $lines 0]] ,]
        set pi [lsearch -exact $columns pwm_in_IBUF]
        if {$pi<0} {error "缺少生产版PWM输入探针"}
        set previous ""
        foreach line [lrange $lines 2 end] {
            set p [lindex [split [string trim $line] ,] $pi]
            if {$previous ne "" && $p ne $previous} {incr activity}
            set previous $p
        }
        puts "ACTIVITY_CAPTURE=$n transitions_cumulative=$activity"
        flush stdout
    }
    puts $fd "coarse_pwm_transitions=$activity"
    if {$activity==0} {
        puts $fd "A=NOT_ARMED_NO_INPUT_ACTIVITY\nB=NOT_ARMED_NO_INPUT_ACTIVITY"
    } else {
        set valid [get_hw_probes -of_objects $ila -filter {NAME =~ *error_valid_100m*}]
        set code [get_hw_probes -of_objects $ila -filter {NAME =~ *error_code_100m*}]
        if {[llength $valid]!=1 || [llength $code]!=1} {error "错误事件探针不唯一"}
        set_property TRIGGER_COMPARE_VALUE "eq1'b1" $valid
        foreach {label value} {A 0001 B 0010} {
            set_property TRIGGER_COMPARE_VALUE "eq4'b$value" $code
            set failed [catch {
                run_hw_ila $ila
                wait_on_hw_ila -timeout 0.25 $ila
                set data [upload_hw_ila_data $ila]
                write_hw_ila_data -csv_file $out/ERROR_${label}_100M.csv $data
                write_hw_ila_data $out/ERROR_${label}_100M.ila $data
            } reason]
            if {$failed} {catch {stop_hw_ila $ila}}
            puts $fd "trigger_$label=[expr {$failed ? {NOT_CAPTURED} : {CAPTURED}}]; reason=$reason"
            flush $fd
            puts "ERROR_${label}_100M=[expr {$failed ? {NOT_CAPTURED} : {CAPTURED}}]"
            flush stdout
        }
    }
} reason]
puts $fd "attempt_status=[expr {$rc ? {FAILED} : {COMPLETED}}]\nreason=$reason"
close $fd
if {$opened} {catch {close_hw_target}}
catch {close_hw_manager}
if {$rc} {puts stderr "BOARD_ATTEMPT_FAILED=$reason";exit 1}
puts "BOARD_ATTEMPT_COMPLETE"

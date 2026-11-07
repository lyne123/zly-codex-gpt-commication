# 本次用户已授权上板；只配置FPGA易失存储，不访问Flash或修改工程。
source -encoding utf-8 [lindex $argv 0]
set opened 0
set f [open $capture_dir/HARDWARE_STATUS.txt w]
fconfigure $f -encoding utf-8
puts $f "programming=volatile_FPGA_RAM\nflash_programmed=0\nBIT=$bit_file\nLTX=$ltx_file"
set rc [catch {
    open_hw_manager
    connect_hw_server -url localhost:3121 -cs_url TCP:127.0.0.1:3042
    set targets [get_hw_targets -quiet]
    puts $f "targets=$targets"
    set target [get_hw_targets -quiet -filter {NAME =~ *C3067D03ABCD*}]
    if {[llength $target]!=1} {error "没有唯一的既有C306板卡，不烧录其他目标"}
    set_property PARAM.FREQUENCY 1000000 $target
    open_hw_target $target
    set opened 1
    set dev [get_hw_devices -quiet -filter {PART =~ xc7k325t*}]
    if {[llength $dev]!=1} {error "需要唯一XC7K325T器件"}
    current_hw_device $dev
    puts $f "target=$target\npart=[get_property PART $dev]"
    flush $f
    set_property PROGRAM.FILE $bit_file $dev
    set_property PROBES.FILE $ltx_file $dev
    set_property FULL_PROBES.FILE $ltx_file $dev
    if {![info exists program_requested] || $program_requested} {
        puts $f "programming_started=1"
        puts "CORRECTED_PROGRAM_START"
        flush stdout
        program_hw_devices $dev
        puts $f "programming_completed=1"
    } else {
        # 只复读刚刚完成的配置，不复位、不重烧，保留原测量通路连续运行。
        puts $f "programming_started=0\nexisting_configuration_reused=1"
        puts "CORRECTED_REUSE_CONFIGURATION_NO_REPROGRAMMING"
    }
    flush $f
    after 2000
    refresh_hw_device $dev
    set cfg [open $capture_dir/CONFIG_AFTER.txt w]
    foreach p [lsort [list_property $dev]] {
        if {[string match REGISTER.CONFIG_STATUS* $p] || [string match REGISTER.BOOT_STATUS* $p]} {
            if {![catch {get_property $p $dev} value]} {puts $cfg "$p=$value"}
        }
    }
    close $cfg
    if {[get_property REGISTER.CONFIG_STATUS.BIT14_DONE_PIN $dev]!=1 ||
        [get_property REGISTER.CONFIG_STATUS.BIT00_CRC_ERROR $dev]!=0 ||
        [get_property REGISTER.CONFIG_STATUS.BIT15_IDCODE_ERROR $dev]!=0} {error "配置状态未通过DONE/CRC/IDCODE检查"}
    foreach {name expected} {u_ila2 C83C094952F254A2A90834971C4269BE u_ila3 005AAA8F6BEB5365914C104C10152EC8} {
        set ila [get_hw_ilas -of_objects $dev -filter "CELL_NAME == $name"]
        if {[llength $ila]!=1 || [string toupper [get_property CORE_UUID $ila]] ne $expected} {error "$name 与本次LTX不匹配"}
        puts $f "$name=[get_property CORE_UUID $ila]"
    }
    puts "CORRECTED_CONFIG_AND_TWO_ILAS_VERIFIED"
    flush stdout
    set ila [get_hw_ilas -of_objects $dev -filter {CELL_NAME == u_ila3}]
    foreach p [get_hw_probes -of_objects $ila] {
        set_property DISPLAY_RADIX UNSIGNED $p
        set width [get_property WIDTH $p]
        set_property TRIGGER_COMPARE_VALUE "eq${width}'b[string repeat X $width]" $p
    }
    set_property CONTROL.DATA_DEPTH 2048 $ila
    set_property CONTROL.WINDOW_COUNT 1 $ila
    set_property CONTROL.TRIGGER_POSITION 0 $ila
    set count 0
    set limit [expr {[info exists max_windows] ? $max_windows : 3}]
    set goal [expr {[info exists target_valid] ? $target_valid : 0}]
    for {set n 1} {$n<=$limit && (!$goal || $count<$goal)} {incr n} {
        run_hw_ila -trigger_now $ila
        wait_on_hw_ila -timeout 0.1 $ila
        set data [upload_hw_ila_data $ila]
        set output $capture_dir/[format "ACTIVITY_%02d.csv" $n]
        if {[file exists $output]} {error "禁止覆盖已有原始采集"}
        write_hw_ila_data -csv_file $output $data
        # 复用既有采集流程的valid计数规则；所有记录都保留，不筛选离群脉宽。
        set stream [open $output r]
        set lines [split [string trim [read $stream]] \n]
        close $stream
        if {[llength $lines]!=2050} {error "ILA导出行数不完整，保留文件"}
        set columns [split [string trim [lindex $lines 0]] ,]
        set vi [lsearch -exact $columns pulse_width_valid_100m]
        set wi [lsearch -glob $columns {pulse_width_ps_100m*}]
        if {$vi<0 || $wi<0} {error "缺少有效位或脉宽列"}
        set batch_count 0
        foreach line [lrange $lines 2 end] {
            set fields [split [string trim $line] ,]
            set value [lindex $fields $wi]
            if {[lindex $fields $vi] eq "1" && [string is integer -strict $value] && $value>=0 && $value<2048000} {incr batch_count}
        }
        incr count $batch_count
        puts "CORRECTED_ACTIVITY_CAPTURE=$n VALID=$batch_count TOTAL=$count TARGET=$goal"
        flush stdout
    }
    puts $f "configuration_verified=1\nILA_activity_windows=[expr {$n-1}]\nvalid_measurements=$count\ntarget_valid=$goal"
    if {$goal && $count<$goal} {error "有效测量不足；保留全部已完成窗口"}
} reason]
puts $f "attempt_status=[expr {$rc ? {FAILED} : {COMPLETED}}]\nreason=$reason"
close $f
if {$opened} {catch {close_hw_target}}
catch {close_hw_manager}
if {$rc} {puts stderr "CORRECTED_BOARD_FAILED=$reason";exit 1}
puts "CORRECTED_BOARD_BRINGUP_COMPLETE"

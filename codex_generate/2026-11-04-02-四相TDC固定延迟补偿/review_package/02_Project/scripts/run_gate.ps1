param(
    [ValidateSet('baseline','compensated')][string]$Variant='baseline',
    [ValidateSet('smoke','calibration','validation','fifo_probe')][string]$Dataset='calibration',
    [ValidateSet('sim_1','fifo_probe')][string]$Simset='sim_1',
    [switch]$Prepare,
    [string]$VivadoBin='F:\Xilinx\Vivado\2022.2\bin'
)
$ErrorActionPreference='Stop'
if ($Dataset -eq 'fifo_probe' -and $Simset -ne 'fifo_probe') { throw '错误FIFO诊断必须使用独立fifo_probe仿真集' }
if (-not (Test-Path -LiteralPath 'T:\scripts\prepare_sim.tcl')) { throw '先按REPRODUCE.md映射T盘' }
$env:TDC_TASK_ROOT='T:/'
$env:PATH="$VivadoBin;$env:PATH"
$work="T:\build\${Variant}_ascii\tdc_${Variant}.sim\$Simset\impl\timing\xsim"
$out="T:\results\$Variant\gate_$Dataset"
New-Item -ItemType Directory -Path $out -Force | Out-Null
if (Test-Path -LiteralPath "$out\widths.csv") { throw '拒绝覆盖已有测量，请在新的任务副本中复跑' }
if ($Prepare) {
    & "$VivadoBin\vivado.bat" -mode batch -source T:/scripts/prepare_sim.tcl -tclargs $Variant $Simset -log "T:/logs/${Variant}_${Simset}_prepare.log" -journal "T:/logs/${Variant}_${Simset}_prepare.jou" *> "T:/logs/${Variant}_${Simset}_prepare_console.log"
    if ($LASTEXITCODE -ne 0) { throw '导出仿真脚本失败' }
    Push-Location -LiteralPath $work
    try {
        & .\compile.bat *> "T:/logs/${Variant}_${Simset}_compile_console.log"
        if ($LASTEXITCODE -ne 0) { throw '网表编译失败' }
        & .\elaborate.bat *> "T:/logs/${Variant}_${Simset}_elaborate_console.log"
        if ($LASTEXITCODE -ne 0) { throw 'SDF展开失败' }
        Copy-Item -LiteralPath 'T:\sim\tb_tdc.sv' -Destination "$work\prepared_tb.sv"
    } finally { Pop-Location }
}
if (-not (Test-Path -LiteralPath "$work\prepared_tb.sv")) { throw '缺少编译时测试平台快照，请在新输出目录使用-Prepare' }
Copy-Item -LiteralPath "$work\prepared_tb.sv" -Destination "$out\input_tb.sv"
Copy-Item -LiteralPath "T:\sim\stimuli\${Dataset}.txt" -Destination "$out\stimulus.txt"
Copy-Item -LiteralPath "T:\sim\stimuli\${Dataset}_truth.csv" -Destination "$out\truth.csv"
Copy-Item -LiteralPath "$work\elaborate.log" -Destination "$out\elaboration.log"
if ($Simset -eq 'sim_1') {
    Copy-Item -LiteralPath "$work\tb_tdc_time_impl.sdf" -Destination "T:\results\$Variant\annotated_design.sdf" -Force
    Copy-Item -LiteralPath "$work\tb_tdc_time_impl.v" -Destination "T:\results\$Variant\annotated_design.v" -Force
}
$files=@("$out\input_tb.sv","T:\sim\stimuli\$Dataset.txt","$work\tb_tdc_time_impl.sdf","$work\tb_tdc_time_impl.v","T:\results\$Variant\design.dcp")
$files | Get-FileHash -Algorithm SHA256 | Select-Object Path,Hash | ConvertTo-Json | Set-Content -LiteralPath "$out\input_sha256.json" -Encoding utf8
Push-Location -LiteralPath $work
try {
    # 与Vivado导出的批处理入口保持相同参数传递方式，避免PowerShell重写等号参数。
    Copy-Item -LiteralPath 'T:\scripts\run_all.tcl' -Destination "$work\run_all.tcl" -Force
    $batch="@echo off`r`ncall `"$VivadoBin\xsim.bat`" tb_tdc_time_impl -tclbatch run_all.tcl -log ${Variant}_${Dataset}.log -testplusarg `"STIMULUS=T:/sim/stimuli/$Dataset.txt`" -testplusarg `"OUTPUT_DIR=T:/results/$Variant/gate_$Dataset`"`r`nexit /b %errorlevel%`r`n"
    [System.IO.File]::WriteAllText("$out\run_xsim.bat",$batch,[System.Text.Encoding]::ASCII)
    $stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
    & "$out\run_xsim.bat" *> "T:/logs/${Variant}_${Dataset}_xsim_${stamp}_console.log"
    if (Test-Path -LiteralPath "$work\${Variant}_${Dataset}.log") {
        Copy-Item -LiteralPath "$work\${Variant}_${Dataset}.log" -Destination "$out\simulation.log"
    }
    if ($LASTEXITCODE -ne 0) { throw '时序仿真进程失败' }
} finally { Pop-Location }
if (-not (Select-String -LiteralPath "$out\simulation.log" -Pattern 'TDC_SIM_DONE' -Quiet)) { throw '未观察到测试平台正常结束标记' }
@("vivado=2022.2","level=gate","variant=$Variant","dataset=$Dataset","timing_checks=enabled","annotation=see elaboration.log and input_sha256.json","wave_logging=disabled; CSV and warning logs retained") | Set-Content -LiteralPath "$out\run_manifest.txt" -Encoding utf8
Write-Output "时序仿真完成：$out"

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('generate','test-scripts','rtl','test-compensation','build-baseline','gate-smoke','gate-calibration','calibrate','build-compensated','gate-baseline-validation','gate-compensated-validation','fifo-probes','analyze','all')]
    [string]$Stage,
    [string]$Vivado='F:\Xilinx\Vivado\2022.2\bin\vivado.bat',
    [string]$Iverilog='F:\iverilog\bin\iverilog.exe',
    [string]$Vvp='F:\iverilog\bin\vvp.exe',
    [string]$Python='python',
    [string]$PlotPython='D:\00-code\FPGA_Prj\fpga_tdc_v3\codex_generate\.venv-rms-stable\Scripts\python.exe'
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$env:PYTHONUTF8='1'
if ($Stage -eq 'all') {
    foreach ($next in @('generate','test-scripts','rtl','test-compensation','build-baseline','gate-smoke','gate-calibration','calibrate','build-compensated','gate-baseline-validation','gate-compensated-validation','fifo-probes','analyze')) {
        & $PSCommandPath -Stage $next -Vivado $Vivado -Iverilog $Iverilog -Vvp $Vvp -Python $Python -PlotPython $PlotPython
        if (-not $?) { throw "阶段失败：$next" }
    }
    exit 0
}
Push-Location -LiteralPath $taskRoot
try {
    if ($Stage -eq 'generate' -or $Stage -eq 'test-scripts' -or $Stage -eq 'calibrate' -or $Stage -eq 'analyze') {
        switch ($Stage) {
            'generate' { & $Python scripts/experiment.py generate }
            'test-scripts' { & $Python scripts/test_experiment.py }
            'calibrate' { & $Python scripts/experiment.py calibrate results/baseline/gate_calibration }
            'analyze' {
                & $Python scripts/experiment.py analyze results/baseline/gate_validation
                if ($LASTEXITCODE -ne 0) { throw 'baseline分析失败' }
                & $Python scripts/experiment.py analyze results/compensated/gate_validation
                if ($LASTEXITCODE -ne 0) { throw 'compensated分析失败' }
                & $Python scripts/compare.py
                if ($LASTEXITCODE -ne 0) { throw '逐事件比较失败' }
                foreach ($variant in @('baseline','compensated')) {
                    & $Python scripts/audit_sdf.py $variant
                    if ($LASTEXITCODE -ne 0) { throw 'SDF核对失败' }
                }
                & $PlotPython -B scripts/plot_results.py
                if ($LASTEXITCODE -ne 0) { throw '绘图失败' }
                & $Python scripts/report.py
            }
        }
        if ($LASTEXITCODE -ne 0) { throw "阶段失败：$Stage" }
    } elseif ($Stage -eq 'rtl' -or $Stage -eq 'test-compensation') {
        if ($Stage -eq 'rtl') {
            New-Item -ItemType Directory -Path results/bypass/rtl_validation -Force | Out-Null
            if (Test-Path -LiteralPath results/bypass/rtl_validation/widths.csv) { throw '拒绝覆盖已有RTL回归数据' }
            Copy-Item -LiteralPath sim/stimuli/validation_truth.csv -Destination results/bypass/rtl_validation/truth.csv
            Copy-Item -LiteralPath sim/stimuli/validation.txt -Destination results/bypass/rtl_validation/stimulus.txt
            $rtlFiles=@(Get-ChildItem -LiteralPath rtl -Filter '*.v' | ForEach-Object FullName)
            & $Iverilog -g2012 -s tb_tdc -o build/rtl_validation.vvp sim/tb_tdc.sv sim/functional_models.v @rtlFiles *> logs/rtl_replay_compile.log
            if ($LASTEXITCODE -ne 0) { throw 'RTL编译失败' }
            & $Vvp build/rtl_validation.vvp +STIMULUS=sim/stimuli/validation.txt +OUTPUT_DIR=results/bypass/rtl_validation *> logs/rtl_replay.log
            if ($LASTEXITCODE -ne 0) { throw 'RTL仿真失败' }
            & $Python scripts/check_functional.py results/bypass/rtl_validation
        } else {
            $original=(Get-Content -LiteralPath baseline/rtl/tdc_time_locate.v -Raw).Replace('module tdc_time_locate #(', 'module tdc_time_locate_original #(')
            [System.IO.File]::WriteAllText((Join-Path $taskRoot 'build/tdc_time_locate_original.v'),$original,[System.Text.UTF8Encoding]::new($false))
            & $Iverilog -g2012 -s tb_compensation -o build/compensation.vvp sim/tb_compensation.sv build/tdc_time_locate_original.v rtl/tdc_time_locate.v *> logs/compensation_compile.log
            if ($LASTEXITCODE -ne 0) { throw '补偿单元测试编译失败' }
            & $Vvp build/compensation.vvp *> logs/compensation_test.log
            Get-Content -LiteralPath logs/compensation_test.log
        }
        if ($LASTEXITCODE -ne 0) { throw "阶段失败：$Stage" }
    } else {
        # T盘只是本任务目录的临时短路径，实际产物仍归档于中文日期目录。
        $mappings=@(& subst)
        $existing=@($mappings | Where-Object { $_ -match '^T:\\:' })
        if ($existing.Count -gt 0) {
            $mappedTarget=($existing[0] -split ' => ',2)[1]
            if ($mappedTarget.TrimEnd('\') -ine $taskRoot.TrimEnd('\')) { throw 'T盘映射属于其他任务，请先选择空闲盘符并同步修改本脚本' }
        } elseif (Test-Path -LiteralPath 'T:\') { throw 'T盘已占用，拒绝覆盖' }
        else { & subst T: $taskRoot; if ($LASTEXITCODE -ne 0) { throw '创建短路径失败' } }
        $env:TDC_TASK_ROOT='T:/'
        if ($Stage -eq 'fifo-probes') {
            & $Python scripts/check_error_fifo.py generate
            if ($LASTEXITCODE -ne 0) { throw '生成错误FIFO诊断失败' }
            foreach ($variant in @('baseline','compensated')) {
                & "$PSScriptRoot\run_gate.ps1" -Variant $variant -Dataset fifo_probe -Simset fifo_probe -Prepare -VivadoBin (Split-Path -Path $Vivado -Parent)
                & $Python scripts/check_error_fifo.py $variant
                if ($LASTEXITCODE -ne 0) { throw '错误FIFO诊断失败' }
            }
            return
        }
        if ($Stage -like 'gate-*') {
            switch ($Stage) {
                'gate-smoke' { & "$PSScriptRoot\run_gate.ps1" -Variant baseline -Dataset smoke -Prepare -VivadoBin (Split-Path -Path $Vivado -Parent) }
                'gate-calibration' { & "$PSScriptRoot\run_gate.ps1" -Variant baseline -Dataset calibration -VivadoBin (Split-Path -Path $Vivado -Parent) }
                'gate-baseline-validation' { & "$PSScriptRoot\run_gate.ps1" -Variant baseline -Dataset validation -VivadoBin (Split-Path -Path $Vivado -Parent) }
                'gate-compensated-validation' { & "$PSScriptRoot\run_gate.ps1" -Variant compensated -Dataset validation -Prepare -VivadoBin (Split-Path -Path $Vivado -Parent) }
            }
            if (-not $?) { throw "SDF阶段失败：$Stage" }
            return
        }
        $arguments=switch($Stage) {
            'build-baseline' { @('T:/scripts/build.tcl','baseline') }
            'build-compensated' { @('T:/scripts/build.tcl','compensated') }
            'gate-smoke' { @('T:/scripts/run_sim.tcl','baseline','smoke','gate') }
            'gate-calibration' { @('T:/scripts/run_sim.tcl','baseline','calibration','gate') }
            'gate-baseline-validation' { @('T:/scripts/run_sim.tcl','baseline','validation','gate') }
            'gate-compensated-validation' { @('T:/scripts/run_sim.tcl','compensated','validation','gate') }
        }
        $script=$arguments[0]
        $scriptArgs=$arguments[1..($arguments.Count-1)]
        $stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
        & $Vivado -mode batch -source $script -tclargs @scriptArgs -log "T:/logs/${Stage}_${stamp}.log" -journal "T:/logs/${Stage}_${stamp}.jou" *> "T:/logs/${Stage}_${stamp}_console.log"
        if ($LASTEXITCODE -ne 0) { throw "Vivado阶段失败：$Stage；详见logs" }
    }
} finally { Pop-Location }

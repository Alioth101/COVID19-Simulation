@echo off
REM Server experiment runner with comprehensive logging (Windows)
REM Usage: run_experiment_with_logging.bat

REM Create timestamp for this run
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "TIMESTAMP=%YYYY%%MM%%DD%_%HH%%Min%%Sec%"

set "LOG_DIR=output\graph_batch"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Define log files
set "CONSOLE_LOG=%LOG_DIR%\console_output_%TIMESTAMP%.log"
set "ERROR_LOG=%LOG_DIR%\error_output_%TIMESTAMP%.log"
set "COMBINED_LOG=%LOG_DIR%\combined_output_%TIMESTAMP%.log"

echo 🚀 Starting experiment with comprehensive logging...
echo 📝 Console output: %CONSOLE_LOG%
echo ❌ Error output: %ERROR_LOG%
echo 📋 Combined output: %COMBINED_LOG%
echo.

REM Run the experiment with output redirection
python run_graph_llm_batch.py > "%COMBINED_LOG%" 2>&1

echo.
echo ✅ Experiment completed!
echo 📁 All logs saved in: %LOG_DIR%
echo.
echo 📋 Next steps:
echo   1. python sort_debug_logs.py
echo   2. python analyze_economic_debug.py
echo   3. Review logs: %COMBINED_LOG%

pause

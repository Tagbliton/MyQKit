@echo off
REM 切换到脚本所在目录
cd /d "%~dp0"

REM 1. 在同一个窗口后台启动 new_data.py
start /b "" ".venv\Scripts\python.exe" new_data.py

REM 1. 在同一个窗口后台启动 new_data.py
start /b "" ".venv\Scripts\python.exe" CsvAndPraquet.py

REM 2. 启动 Web 服务（放在后台，以便后续命令可以继续执行）
start /b "" ".venv\Scripts\python.exe" run_web.py --port 8765
start /b "" ".venv\Scripts\python.exe" AlphaManager.py --port 8766

REM 3. 等待 3 秒，确保 Web 服务已完全初始化并监听端口
timeout /t 3 /nobreak >nul

REM 4. 打开网页
start http://127.0.0.1:8765/
start http://127.0.0.1:8766/

echo ========================================================
echo 服务已启动，请勿关闭此窗口（关闭窗口将终止所有后台服务）。
echo ========================================================

REM 保持窗口运行
pause >nul
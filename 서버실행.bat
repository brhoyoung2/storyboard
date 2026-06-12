@echo off
REM 이 배치 파일을 더블클릭하면 항상 올바른 폴더에서 서버가 실행됩니다.
REM %~dp0 = 이 .bat 파일이 있는 폴더(=프로젝트 루트)
cd /d "%~dp0"

echo ============================================
echo   geulconti -^> geurimconti  server start
echo   close: press Ctrl+C in this window
echo ============================================
echo.

python src/server.py
if errorlevel 1 (
  echo.
  echo [python failed] trying "py" launcher...
  py src/server.py
)

echo.
echo (server stopped)
pause

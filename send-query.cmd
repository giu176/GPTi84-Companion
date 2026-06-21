@echo off
setlocal
set "ROOT=%~dp0"
set "PORT=%~1"
if "%PORT%"=="" set "PORT=COM3"

if exist "%ROOT%.venv\Scripts\python.exe" (
  "%ROOT%.venv\Scripts\python.exe" "%ROOT%tools\file_relay\relay_query.py" --port "%PORT%" --query "%ROOT%query.txt" --reply "%ROOT%query_reply.txt"
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%ROOT%tools\file_relay\relay_query.py" --port "%PORT%" --query "%ROOT%query.txt" --reply "%ROOT%query_reply.txt"
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%ROOT%tools\file_relay\relay_query.py" --port "%PORT%" --query "%ROOT%query.txt" --reply "%ROOT%query_reply.txt"
  exit /b %ERRORLEVEL%
)

echo Python 3 was not found. Create .venv as described in README.md.
exit /b 2


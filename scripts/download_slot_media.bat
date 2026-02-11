@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================
REM Fill these values:
set "VPS_HOST=108.181.252.78"
set "VPS_USER=root"
set "SLOT_DEFAULT=1"
REM ============================

set /p SLOT_NUMBER=Enter slot number (1-15) [default %SLOT_DEFAULT%]: 
if not defined SLOT_NUMBER set "SLOT_NUMBER=%SLOT_DEFAULT%"

for /f "delims=0123456789" %%A in ("%SLOT_NUMBER%") do (
  echo [ERROR] SLOT_NUMBER must be numeric from 1 to 15.
  exit /b 1
)

if %SLOT_NUMBER% LSS 1 (
  echo [ERROR] SLOT_NUMBER must be from 1 to 15.
  exit /b 1
)
if %SLOT_NUMBER% GTR 15 (
  echo [ERROR] SLOT_NUMBER must be from 1 to 15.
  exit /b 1
)

if %SLOT_NUMBER% LSS 10 (
  set "SLOT_PAD=00%SLOT_NUMBER%"
) else (
  set "SLOT_PAD=0%SLOT_NUMBER%"
)

set "BASE_DIR=D:\dslr_tmp_media"
set "TARGET_DIR=%BASE_DIR%\slot!SLOT_PAD!"
set "REMOTE_SLOT=slot-!SLOT_PAD!"

where ssh >nul 2>nul
if errorlevel 1 (
  echo [ERROR] ssh.exe not found in PATH.
  echo Install OpenSSH Client feature in Windows.
  exit /b 1
)

if not exist "%BASE_DIR%" mkdir "%BASE_DIR%"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

echo Downloading !REMOTE_SLOT! to "%TARGET_DIR%" ...
echo Enter VPS password when ssh asks for it.
echo Download started! Please WAIT until it will be done....
ssh -o StrictHostKeyChecking=accept-new %VPS_USER%@%VPS_HOST% ^
  "sh -lc 'echo Success: SSH authentication passed. 1>&2; cd /opt/photochanger/app && docker compose exec -T app tar -C /app/media/results -czf - !REMOTE_SLOT!'" ^
  | tar -xzvf - -C "%TARGET_DIR%"

if errorlevel 1 (
  echo [ERROR] Download failed.
  exit /b 1
)

echo [OK] Done: "%TARGET_DIR%"
exit /b 0

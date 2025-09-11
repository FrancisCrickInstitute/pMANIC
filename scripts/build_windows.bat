@echo off
setlocal enabledelayedexpansion

REM Build MANIC on Windows using uv (if available) or pip fallback, then Inno Setup

where uv >nul 2>&1
if %ERRORLEVEL%==0 (
  echo Detected uv; using uv for build
  REM Ensure project deps are synced into .venv
  uv venv --clear || goto :error
  uv sync || goto :error
  REM Install PyInstaller into the project environment and run within it
  uv pip install pyinstaller || goto :error
  REM If icon is missing, PyInstaller will run without it (handled in spec)
  uv run pyinstaller -y --clean MANIC.spec || goto :error
) else (
  echo uv not found; falling back to pip
  if not exist .venv (
    py -3.12 -m venv .venv || goto :error
  )
  call .venv\Scripts\activate || goto :error
  pip install --upgrade pip || goto :error
  pip install -r requirements.txt pyinstaller || goto :error
  REM If icon is missing, PyInstaller will run without it (handled in spec)
  pyinstaller -y --clean MANIC.spec || goto :error
)

echo.
echo Built app at dist\MANIC\MANIC.exe
echo.

REM Build installer if Inno Setup is installed
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
  %ISCC% installer\MANIC.iss || goto :error
  echo.
  echo Installer at dist\MANIC-Setup.exe
  echo.
) else (
  echo Inno Setup not found. Skipping installer build.
)

echo Done.
exit /b 0

:error
echo Build failed with error level %errorlevel%.
exit /b %errorlevel%

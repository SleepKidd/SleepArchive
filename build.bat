@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/7] Checking Python 3.12...
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3.12"
) else (
    where python >nul 2>nul || goto :python_error
    set "PYTHON_CMD=python"
)
%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" || goto :python_error

echo [2/7] Preparing virtual environment...
if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv || goto :failed
)
set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

echo [3/7] Installing dependencies...
"%VENV_PYTHON%" -m pip install --upgrade pip || goto :failed
"%VENV_PYTHON%" -m pip install -r requirements.txt || goto :failed

echo [4/7] Generating application icon...
"%VENV_PYTHON%" assets\generate_icon.py || goto :failed
if not exist "assets\SleepArchive.ico" goto :failed

echo [5/7] Running tests...
"%VENV_PYTHON%" -m pytest || goto :tests_failed

echo [6/7] Cleaning old build output...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo [7/7] Building SleepArchive.exe...
"%VENV_PYTHON%" -m PyInstaller --noconfirm --clean SleepArchive.spec || goto :failed
if not exist "dist\SleepArchive.exe" goto :missing_exe

echo.
echo Build completed successfully:
echo %CD%\dist\SleepArchive.exe
exit /b 0

:python_error
echo ERROR: Python 3.12 or newer is required. Install it from python.org.
exit /b 1

:tests_failed
echo ERROR: Tests failed. Build stopped; no executable was produced.
exit /b 1

:missing_exe
echo ERROR: PyInstaller finished without dist\SleepArchive.exe.
exit /b 1

:failed
echo ERROR: Build failed. Review the messages above.
exit /b 1


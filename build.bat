@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem SleepArchive Windows build script.
rem Run normally:       build.bat
rem Recreate the venv:  build.bat --clean

cd /d "%~dp0"
if errorlevel 1 (
    echo ERROR: Cannot open the project directory: "%~dp0"
    exit /b 1
)

set "CLEAN_VENV=0"
if /i "%~1"=="--clean" set "CLEAN_VENV=1"
if not "%~1"=="" if /i not "%~1"=="--clean" (
    echo ERROR: Unknown option "%~1".
    echo Usage: build.bat [--clean]
    exit /b 2
)

echo.
echo ============================================================
echo   SleepArchive - Windows EXE build
echo ============================================================
echo.

echo [1/9] Looking for Python 3.12 or newer...
set "PYTHON_CMD="

rem Prefer the launcher's default Python 3 when it is new enough. This also
rem supports future Python releases without changing this script.
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"
if defined PYTHON_CMD goto :python_found

rem The default launcher version can be old while a suitable version is also
rem installed, so check every currently supported 3.12+ version explicitly.
py -3.14 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.14"
if defined PYTHON_CMD goto :python_found

py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.13"
if defined PYTHON_CMD goto :python_found

py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.12"
if defined PYTHON_CMD goto :python_found

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python"
if defined PYTHON_CMD goto :python_found

python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python3"
if defined PYTHON_CMD goto :python_found

goto :python_error

:python_found
%PYTHON_CMD% -c "import sys; print('Using Python', sys.version.split()[0], 'from', sys.executable)"
if errorlevel 1 goto :python_error

echo.
echo [2/9] Preparing the virtual environment...
if "%CLEAN_VENV%"=="1" if exist ".venv" (
    echo Removing the old .venv because --clean was requested...
    rmdir /s /q ".venv"
    if exist ".venv" goto :venv_remove_error
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
    if errorlevel 1 (
        echo Existing .venv is invalid or uses an old Python. Recreating it...
        rmdir /s /q ".venv"
        if exist ".venv" goto :venv_remove_error
    )
)

if exist ".venv" if not exist ".venv\Scripts\python.exe" (
    echo Existing .venv is incomplete. Recreating it...
    rmdir /s /q ".venv"
    if exist ".venv" goto :venv_remove_error
)

if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv ".venv"
    if errorlevel 1 goto :venv_create_error
)

set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" goto :venv_create_error

echo.
echo [3/9] Updating build tools...
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_NO_INPUT=1"
"%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :pip_error

echo.
echo [4/9] Installing project dependencies...
"%VENV_PYTHON%" -m pip install --prefer-binary -r "%~dp0requirements.txt"
if errorlevel 1 goto :dependency_error

echo.
echo [5/9] Generating the application icon...
"%VENV_PYTHON%" "%~dp0assets\generate_icon.py"
if errorlevel 1 goto :icon_error
if not exist "%~dp0assets\SleepArchive.ico" goto :icon_error

echo.
echo [6/9] Checking Python sources...
"%VENV_PYTHON%" -m ruff check .
if errorlevel 1 goto :lint_error

echo.
echo [7/9] Running automated tests...
set "QT_QPA_PLATFORM=offscreen"
"%VENV_PYTHON%" -m pytest -q
if errorlevel 1 goto :tests_error

echo.
echo [8/9] Cleaning previous build output...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "build" goto :clean_error
if exist "dist" goto :clean_error

echo.
echo [9/9] Building SleepArchive.exe...
"%VENV_PYTHON%" -m PyInstaller --noconfirm --clean "%~dp0SleepArchive.spec"
if errorlevel 1 goto :pyinstaller_error
if not exist "%~dp0dist\SleepArchive.exe" goto :missing_exe

for %%F in ("%~dp0dist\SleepArchive.exe") do set "EXE_SIZE=%%~zF"
if not defined EXE_SIZE goto :missing_exe
if %EXE_SIZE% LSS 1048576 goto :invalid_exe

echo.
echo ============================================================
echo   BUILD COMPLETED SUCCESSFULLY
echo ============================================================
echo   Output: "%~dp0dist\SleepArchive.exe"
echo   Size:   %EXE_SIZE% bytes
echo.
exit /b 0

:python_error
echo.
echo ERROR: Python 3.12 or newer was not found.
echo Install 64-bit Python from https://www.python.org/downloads/windows/
echo During installation enable "Add python.exe to PATH", then run build.bat again.
exit /b 10

:venv_remove_error
echo.
echo ERROR: Cannot remove the old .venv directory.
echo Close Python, SleepArchive, editors and terminals using this folder,
echo then run: build.bat --clean
exit /b 11

:venv_create_error
echo.
echo ERROR: Failed to create .venv.
echo Make sure the Python installation includes pip and the venv module.
exit /b 12

:pip_error
echo.
echo ERROR: Failed to update pip/setuptools/wheel.
echo Check your internet connection, proxy, antivirus and available disk space.
exit /b 13

:dependency_error
echo.
echo ERROR: Failed to install the project dependencies.
echo For a completely fresh retry run: build.bat --clean
exit /b 14

:icon_error
echo.
echo ERROR: Failed to generate assets\SleepArchive.ico.
exit /b 15

:tests_error
echo.
echo ERROR: Automated tests failed. The EXE was not built.
echo Review the failed test shown above before retrying.
exit /b 16

:lint_error
echo.
echo ERROR: Static source checks failed. The EXE was not built.
echo Review the error shown above before retrying.
exit /b 21

:clean_error
echo.
echo ERROR: Cannot clean build or dist.
echo Close a running SleepArchive.exe and any Explorer window using these folders.
exit /b 17

:pyinstaller_error
echo.
echo ERROR: PyInstaller failed to build SleepArchive.exe.
echo Review the PyInstaller error above. A clean retry is: build.bat --clean
exit /b 18

:missing_exe
echo.
echo ERROR: PyInstaller reported success but dist\SleepArchive.exe is missing.
exit /b 19

:invalid_exe
echo.
echo ERROR: dist\SleepArchive.exe is unexpectedly small and is not a valid build.
exit /b 20

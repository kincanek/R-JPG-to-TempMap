@echo off
REM Build the Windows .exe distribution for R-JPG-to-TempMap.
REM
REM Prerequisites (one-time):
REM     pip install -r requirements.txt
REM     pip install pyinstaller
REM
REM Output:
REM     dist\RJPG-to-TempMap\RJPG-to-TempMap.exe   (main launcher)
REM     dist\RJPG-to-TempMap\*.dll / *.pyd         (runtime)
REM     dist\RJPG-to-TempMap\plugins\              (DJI SDK + ExifTool)

setlocal
cd /d "%~dp0"

echo Cleaning previous build output...
if exist build\RJPG-to-TempMap rmdir /s /q build\RJPG-to-TempMap
if exist dist\RJPG-to-TempMap  rmdir /s /q dist\RJPG-to-TempMap

echo Running PyInstaller...
python -m PyInstaller --noconfirm --clean build\RJPG-to-TempMap.spec
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo.
echo Build complete: dist\RJPG-to-TempMap\RJPG-to-TempMap.exe
endlocal

@echo off
setlocal EnableDelayedExpansion

echo ==========================================
echo Annapurna RAW Data Organizer
echo ==========================================
echo.

if not exist raw mkdir raw

for %%F in (sales\*.csv) do (
    set "FILE=%%~nxF"

    rem Extract store and date from filename
    for /f "tokens=2,3 delims=_" %%A in ("%%~nF") do (
        set "STORE=%%A"
        set "DATE=%%B"
    )

    rem Remove resend suffix from date if present
    set "DATE=!DATE:__R1=!"
    set "DATE=!DATE:__R2=!"

    set "YEAR=!DATE:~0,4!"
    set "MONTH=!DATE:~4,2!"

    set "DEST=raw\year=!YEAR!\month=!MONTH!\store=!STORE!"

    if not exist "!DEST!" mkdir "!DEST!"

    copy /Y "%%F" "!DEST!\%%~nxF" >nul

    echo Copied %%~nxF
)

echo.
echo ==========================================
echo RAW ORGANIZATION COMPLETE
echo ==========================================
pause
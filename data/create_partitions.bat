@echo off
setlocal EnableDelayedExpansion

echo ==========================================
echo ANNAPURNA - RAW DATA PARTITIONING
echo ==========================================
echo.

if not exist raw mkdir raw

for %%F in (sales\*.csv) do (

    set "NAME=%%~nF"

    rem Extract store and date from filename
    rem Example: SALES_S01_20240702__R1
    for /f "tokens=2,3 delims=_" %%A in ("!NAME!") do (
        set "STORE=%%A"
        set "DATE=%%B"
    )

    rem Remove resend suffixes
    set "DATE=!DATE:__R1=!"
    set "DATE=!DATE:__R2=!"

    rem Extract year and month
    set "YEAR=!DATE:~0,4!"
    set "MONTH=!DATE:~4,2!"

    rem Create partition directory
    set "DEST=raw\year=!YEAR!\month=!MONTH!\store=!STORE!"

    if not exist "!DEST!" mkdir "!DEST!"

    copy /Y "%%F" "!DEST!\%%~nxF" >nul

    echo Processed %%~nxF
)

echo.
echo ==========================================
echo PARTITIONING COMPLETE
echo ==========================================
echo.
pause
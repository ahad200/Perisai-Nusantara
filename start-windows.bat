@echo off
REM ==========================================================================
REM  PN-X - Nyalakan backend + frontend (Windows).
REM    start-windows.bat        -> hanya bisa dibuka dari laptop ini
REM    start-windows.bat lan    -> juga bisa dibuka perangkat lain di WiFi/LAN yang sama
REM  Tutup kedua jendela "PN-X Backend" / "PN-X Frontend" untuk mematikan.
REM ==========================================================================
setlocal
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\uvicorn.exe" (
  echo Belum di-setup. Jalankan setup-windows.bat terlebih dahulu.
  pause
  exit /b 1
)

set "VITE_HOST="
if /i "%~1"=="lan" set "VITE_HOST=--host"

start "PN-X Backend" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "PN-X Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --port 5173 %VITE_HOST%"

echo Menunggu server siap...
timeout /t 8 /nobreak >nul
start "" http://localhost:5173

echo.
echo  Aplikasi : http://localhost:5173
echo  API docs : http://localhost:8000/docs
echo  Login    : operator / commander / intel / auditor  (password: ChangeMe123!)
if defined VITE_HOST (
  echo  LAN      : buka http://IP-LAPTOP-INI:5173 dari perangkat lain - lihat alamat "Network" di jendela PN-X Frontend
  echo             Jika diminta Windows Firewall, pilih "Allow".
)
echo.
pause

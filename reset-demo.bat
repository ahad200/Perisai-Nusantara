@echo off
REM PN-X - Kembalikan data demo ke kondisi awal (hapus semua data lalu isi ulang).
setlocal
cd /d "%~dp0backend"
echo PERINGATAN: semua data demo (termasuk audit log demo) akan dihapus dan dibuat ulang.
choice /m "Lanjutkan"
if errorlevel 2 exit /b 0
.venv\Scripts\python -m app.demo --reset
pause

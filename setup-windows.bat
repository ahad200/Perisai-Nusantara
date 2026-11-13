@echo off
REM ==========================================================================
REM  PN-X - Setup sekali jalan (Windows). Double-click atau jalankan di CMD.
REM  Butuh: Python 3.12+ dan Node.js 20+ (centang "Add to PATH" saat install).
REM ==========================================================================
setlocal
cd /d "%~dp0"

echo [1/5] Cek Python dan Node.js...
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (where py >nul 2>nul && set "PY=py -3")
if not defined PY (
  echo   GAGAL: Python tidak ditemukan. Install dari https://www.python.org/downloads/
  echo          dan centang "Add python.exe to PATH".
  goto :fail
)
where node >nul 2>nul || (
  echo   GAGAL: Node.js tidak ditemukan. Install versi LTS dari https://nodejs.org/
  goto :fail
)
%PY% --version
node --version

echo [2/5] Virtualenv + dependensi backend...
if not exist "backend\.venv\Scripts\python.exe" (
  %PY% -m venv backend\.venv || goto :fail
)
backend\.venv\Scripts\python -m pip install --upgrade pip >nul
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt || goto :fail

echo [3/5] Konfigurasi backend (.env)...
if not exist "backend\.env" copy "backend\.env.example" "backend\.env" >nul

echo [4/5] Isi data demo (user, aset, serangan simulasi, insiden, playbook)...
pushd backend
.venv\Scripts\python -m app.demo || (popd & goto :fail)
popd

echo [5/5] Dependensi frontend (npm ci, bisa beberapa menit)...
pushd frontend
call npm ci || (popd & goto :fail)
popd

echo.
echo ==== Setup selesai. Jalankan start-windows.bat untuk menyalakan aplikasi. ====
pause
exit /b 0

:fail
echo.
echo ==== Setup GAGAL - lihat pesan di atas. ====
pause
exit /b 1

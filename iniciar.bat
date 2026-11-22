@echo off
setlocal
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=..\Clase E1601.2\puerto-am-bi\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Creando entorno virtual...
  python -m venv .venv
  set "PY=.venv\Scripts\python.exe"
)
if not exist "%PY%" (
  echo No se encontro Python. Instala Python 3.11 o superior.
  pause
  exit /b 1
)

"%PY%" -m pip show fastapi >nul 2>&1 || "%PY%" -m pip install -r requirements.txt

echo.
echo Puerto A&M en http://127.0.0.1:8000
echo Panel administrativo: http://127.0.0.1:8000/admin
echo.
start "" http://127.0.0.1:8000
"%PY%" -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

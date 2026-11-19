@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado. Veja o README.
  pause
  exit /b 1
)
for %%M in (scripts.build_data scripts.build_dw scripts.simulate_sites scripts.export_html) do (
  ".venv\Scripts\python.exe" -m %%M
  if errorlevel 1 (
    echo Falha em %%M.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m streamlit run app.py

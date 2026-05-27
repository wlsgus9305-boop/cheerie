@echo off
chcp 65001 > nul
set "D=%~dp0"
set "PY=%D%.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo ========================================
echo  응원이 공개용 EXE 빌드
echo ========================================

if not exist "%D%icon.ico" (
    echo [오류] icon.ico 없음
    pause
    exit /b 1
)

"%PY%" -m PyInstaller ^
  --onefile ^
  --windowed ^
  --icon "%D%icon.ico" ^
  --add-data "%D%idle.png;." ^
  --add-data "%D%cheer.png;." ^
  --add-data "%D%happy.png;." ^
  --add-data "%D%cheerhot1.png;." ^
  --add-data "%D%cheerhot2.png;." ^
  --hidden-import pynput.keyboard ^
  --hidden-import pynput.mouse ^
  --hidden-import pynput._util.win32 ^
  --collect-all pynput ^
  --noconfirm ^
  --name "Cheerie" ^
  "%D%cheerie.py"

echo.
if exist "%D%dist\Cheerie.exe" (
    echo 완료: dist\Cheerie.exe
) else (
    echo [오류] 빌드 결과를 찾지 못했습니다.
)
pause

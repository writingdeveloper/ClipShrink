@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/3] 의존성 설치...
pip install --upgrade pyinstaller -r requirements.txt || goto :error
echo [2/3] EXE 빌드...
pyinstaller --onefile --noconsole --name ClipShrink --clean ^
  --add-data "clipshrink_app\picker\ui;clipshrink_app/picker/ui" ^
  --collect-all webview clipshrink.py || goto :error
echo [3/3] 완료! 결과물: dist\ClipShrink.exe
echo 실행하면 트레이에 상주합니다. 피커 단축키: Ctrl+Shift+E
pause
exit /b 0
:error
echo 빌드 실패. Python과 pip가 설치되어 있는지 확인하세요.
pause
exit /b 1

@title = Updating modules
@echo off
call "venv/Scripts/activate.bat"
@echo on
"venv/Scripts/Python.exe" -m pip -r install requirements.txt
git pull
@echo off
pause

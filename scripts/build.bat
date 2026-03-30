@echo off
cd %~dp0
cd ..
mkdir temp >nul 2>&1
mkdir output >nul 2>&1
xcopy neuro-implementation\ temp\ /E /I /Y >nul
cd temp
echo Compiling...
..\tools\renpy\renpy.exe . compile

:loop
if exist neuro-implementation.rpyc goto :package
goto :loop

:package
echo Packaging...
python ..\tools\rpatool.py -c neuro-implementation.rpa neuro-implementation.rpyc six.py json py2 websocket
move neuro-implementation.rpa ..\output\ >nul
move neuroconfig.py ..\output\ >nul
cd ..
timeout /t 5 >nul
rd temp /s /q
echo Done!
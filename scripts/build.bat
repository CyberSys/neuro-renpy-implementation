@echo off
cd %~dp0
cd ..

echo Compiling base...
mkdir temp\compile >nul 2>&1
xcopy neuro-implementation\ temp\compile\ /E /I /Y >nul
cd temp\compile
..\..\tools\renpy\renpy.exe . compile
timeout /t 10 >nul
if not exist "neuro-implementation.rpyc" (
    echo RenPy could not compile, exiting...
    cd ..\..
    rd temp /s /q
    exit /b 1
)
cd ..\..

echo Packaging base...
mkdir output\neuro-implementation >nul 2>&1
mkdir temp\package >nul 2>&1
xcopy neuro-implementation\ temp\package\ /E /I /Y >nul
cd temp\package
del *.rpy >nul
move neuroconfig.py ..\..\output\neuro-implementation >nul
xcopy ..\compile\*.rpyc . /E /I /Y >nul
python ..\..\tools\rpatool.py -c neuro-implementation.rpa .
move neuro-implementation.rpa ..\..\output\neuro-implementation >nul
timeout /t 3 >nul
cd ..\..

rd temp /s /q

for /d %%D in (games\*) do (
    echo Compiling %%~nD...
    mkdir temp\compile >nul 2>&1
    xcopy neuro-implementation\ temp\compile\ /E /I /Y >nul
    xcopy %%D temp\compile\ /E /I /Y >nul
    cd temp\compile
    ..\..\tools\renpy\renpy.exe . compile
    timeout /t 10 >nul
    if not exist "neuro-implementation.rpyc" (
        echo RenPy could not compile, exiting...
        cd ..\..
        rd temp /s /q
        exit /b 1
    )
    cd ..\..

    echo Packaging %%~nD...
    mkdir output\neuro-%%~nD-implementation >nul 2>&1
    mkdir temp\package >nul 2>&1
    xcopy neuro-implementation\ temp\package\ /E /I /Y >nul
    xcopy %%D temp\package\ /E /I /Y >nul
    cd temp\package
    move neuroconfig.py ..\..\output\neuro-%%~nD-implementation >nul
    del *.rpy >nul
    xcopy ..\compile\*.rpyc . /E /I /Y >nul
    python ..\..\tools\rpatool.py -c neuro-%%~nD-implementation.rpa .
    move neuro-%%~nD-implementation.rpa ..\..\output\neuro-%%~nD-implementation >nul
    timeout /t 3 >nul
    cd ..\..

    rd temp /s /q
)

echo Done!
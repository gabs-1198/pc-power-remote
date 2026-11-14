@echo off
chcp 65001 >nul
title Instalar PC Power Remote na Inicializacao do Windows
cd /d "%~dp0"

echo ============================================================
echo   CONFIGURANDO PC POWER REMOTE (FIREWALL + INICIALIZACAO)
echo ============================================================
echo.

:: Libera a porta TCP 5050 e UDP 7,9,5051 no Firewall do Windows (Apenas Redes Privadas)
echo [1/2] Configurando regras no Firewall do Windows (Redes Privadas)...
netsh advfirewall firewall delete rule name="PC Power Remote (TCP 5050)" >nul 2>&1
netsh advfirewall firewall add rule name="PC Power Remote (TCP 5050)" dir=in action=allow protocol=TCP localport=5050 profile=private,domain >nul 2>&1
netsh advfirewall firewall delete rule name="PC Power Remote (UDP 7,9,5051)" >nul 2>&1
netsh advfirewall firewall add rule name="PC Power Remote (UDP 7,9,5051)" dir=in action=allow protocol=UDP localport=7,9,5051 profile=private,domain >nul 2>&1

if %errorlevel% equ 0 (
    echo       Regras de Firewall criadas com sucesso!
) else (
    echo       AVISO: Execute este arquivo como Administrador para liberar as portas no Firewall automaticamente.
)

echo [2/2] Criando atalho na Inicializacao do Windows (shell:startup)...
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS_LOADER=%STARTUP_DIR%\PCPowerRemoteAgent.vbs"

(
echo Set WshShell = CreateObject^("WScript.Shell"^)
echo WshShell.CurrentDirectory = "%~dp0"
echo WshShell.Run "pythonw ""%~dp0pc_power_agent.py""", 0, False
) > "%VBS_LOADER%"

echo       Atalho criado em: "%VBS_LOADER%"
echo.
echo Iniciando o agente em segundo plano agora...
wscript.exe "%VBS_LOADER%"

echo.
echo ============================================================
echo   PRONTO! O agente ja esta rodando em segundo plano e
echo   iniciara automaticamente junto com o Windows.
echo ============================================================
pause

@echo off
chcp 65001 >nul
title PC Power Remote - Agente Windows
cd /d "%~dp0"
python pc_power_agent.py
pause

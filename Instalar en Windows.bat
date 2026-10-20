@echo off
rem Puente by Typers: instalador para Windows (doble clic) / Windows installer (double click)
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0herramientas\instalar.ps1"
pause

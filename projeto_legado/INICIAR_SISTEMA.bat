@echo off
title Gerador de Croqui RGE/CPFL
color 0A

echo.
echo  =========================================
echo    GERADOR DE CROQUI RGE/CPFL
echo  =========================================
echo.
echo  Iniciando o sistema...
echo.

cd /d "E:\Projetos\CLAUDE IA\Croqui\CroquiGerador"

:: Abre o navegador automaticamente apos 2 segundos
start "" timeout /t 2 /nobreak >nul
start "" "http://localhost:5000"

:: Inicia o servidor
python app.py

echo.
echo  Sistema encerrado. Pressione qualquer tecla para fechar.
pause >nul

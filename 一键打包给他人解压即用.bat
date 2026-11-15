@chcp 65001 >nul
@echo off
title 一键打包为绿色解压即用版
echo 正在执行自动纯净化打包...
python "%~dp0pack_for_sharing.py"
pause

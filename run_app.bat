@echo off
chcp 65001 > nul
cd /d "D:\红果搭建\gui"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
python -u app.py > stdout.log 2> stderr.log

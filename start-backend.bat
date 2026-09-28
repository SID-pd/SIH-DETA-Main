@echo off
title SIH-DETA Backend API (:8001)
cd /d "%~dp0backend"
set DARPAN_SQLITE_PATH=%~dp0backend\data\darpan.sqlite
echo Starting SIH-DETA Hybrid ML+DSA Backend on http://127.0.0.1:8001 ...
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
pause

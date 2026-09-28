@echo off
title SIH-DETA Frontend Web App (:5173)
cd /d "%~dp0frontend"
echo Starting SIH-DETA Frontend on http://localhost:5173 ...
npm run dev
pause

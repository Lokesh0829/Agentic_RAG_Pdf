@echo off
echo ============================================
echo  Agentic RAG PDF Chatbot - Quick Start
echo ============================================
echo.

echo Starting Backend (FastAPI)...
start "Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\activate.bat && python main.py"

timeout /t 3 /nobreak >nul

echo Starting Frontend (Vite)...
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ============================================
echo  Both services starting...
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:5173
echo  API Docs: http://localhost:8000/docs
echo ============================================
echo.
pause

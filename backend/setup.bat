@echo off
echo ============================================
echo  Agentic RAG PDF Chatbot - Backend Setup
echo ============================================

echo.
echo [1/4] Creating Python 3.11 virtual environment...
py -3.11 -m venv venv

echo.
echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [3/4] Installing Python dependencies...
pip install -r requirements.txt

echo.
echo [4/4] Setup complete!
echo.
echo To start the backend:
echo   venv\Scripts\activate.bat
echo   python main.py
echo.
echo Make sure Ollama is running at http://localhost:11434
echo Make sure MongoDB is running at mongodb://localhost:27017
echo Make sure you have pulled: ollama pull nomic-embed-text
echo.
pause

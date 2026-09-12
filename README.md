# 🤖 Agentic RAG PDF Chatbot

An **Autonomous Multi-Agent RAG** application built with **LangGraph**, **FastAPI**, **ChromaDB**, **MongoDB**, and **React + TypeScript** for intelligent PDF Q&A.

## 🌟 Key Features
- 🧠 **LangGraph Multi-Agent Pipeline**: Adaptive query routing (`query_analyzer`, `retrieval`, `ocr_table`, `research`, `generate_answer`).
- ⚡ **Hybrid Search**: Combines ChromaDB dense embeddings (`all-MiniLM-L6-v2`) and BM25 sparse retrieval using Reciprocal Rank Fusion (RRF).
- 📊 **Table & OCR Extraction**: Native table extraction via PyMuPDF, pdfplumber, and Tesseract OCR.
- 🔄 **Semantic Cache**: MongoDB cosine-similarity cache to avoid redundant LLM queries.
- 🔐 **Auth & User Isolation**: JWT-based authentication and private document storage.

## 🛠️ Tech Stack
- **Backend**: FastAPI, LangGraph, LangChain, Groq API (Llama 3.3 70B), ChromaDB, MongoDB.
- **Frontend**: React 18, TypeScript, Vite, React Router DOM.

## 🚀 Quick Start

### 1. Backend Setup
cd backend
python -m venv venv && venv\Scripts\activate  # Windows
pip install -r requirements.txt
python main.py

### 2. Frontend Setup
cd frontend
npm install
npm run dev

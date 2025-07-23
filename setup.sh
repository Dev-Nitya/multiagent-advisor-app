#!/bin/bash

echo "🚀 Setting up Multi-Agent Startup Advisor"
echo "=========================================="

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install

echo "✅ Frontend setup complete!"
echo ""
echo "🔧 To start the application:"
echo "1. Start the backend: cd backend && python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"
echo "2. Start the frontend: cd frontend && npm start"
echo ""
echo "🌐 The application will be available at:"
echo "- Frontend: http://localhost:3000"
echo "- Backend API: http://localhost:8000"
echo "- API Documentation: http://localhost:8000/docs"

# 🚀 Multi-Agent Startup Advisor

An AI-powered startup idea evaluation platform that uses multiple specialized agents to provide comprehensive analysis and recommendations for your business ideas.

![Multi-Agent Startup Advisor](https://img.shields.io/badge/AI-Powered-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)
![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)
![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-orange.svg)

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

## ✨ Features

### 🧠 **Multi-Agent Analysis**

- **Market Research Agent**: Analyzes market trends, competition, and demand
- **Financial Advisor Agent**: Evaluates financial viability and business model
- **Product Strategist Agent**: Assesses product features and strategy
- **Summary Agent**: Provides consolidated recommendations

### 🎨 **Beautiful UI**

- Dark theme with purple accents
- Responsive design
- Real-time progress tracking
- Formatted analysis results

### ⚡ **Performance Optimized**

- Parallel agent processing
- Streaming responses
- Optimized task execution
- Smart caching capabilities

## 🏗️ Architecture

```mermaid
graph TB
    A[React Frontend] --> B[FastAPI Backend]
    B --> C[LangGraph Workflow]
    C --> D[Market Research Agent]
    C --> E[Financial Advisor Agent]
    C --> F[Product Strategist Agent]
    D --> G[Summary Agent]
    E --> G
    F --> G
    G --> H[Final Recommendation]

    I[OpenAI GPT] --> D
    I --> E
    I --> F
    I --> G

    J[Tavily Search] --> D
    K[Calculator Tools] --> E
```

## 🛠️ Tech Stack

### Backend

- **FastAPI** - High-performance Python web framework
- **CrewAI** - Multi-agent orchestration framework
- **LangGraph** - Workflow management for AI agents
- **LangChain** - LLM integration and tooling
- **OpenAI API** - GPT models for agent reasoning
- **Tavily API** - Web search capabilities
- **Pydantic** - Data validation and serialization

### Frontend

- **React 18** - Modern UI library
- **Axios** - HTTP client for API calls
- **CSS3** - Custom styling with animations

### Tools & Services

- **OpenAI GPT-3.5/4** - Language models
- **Tavily Search** - Web search API
- **Python-dotenv** - Environment management

## 📋 Prerequisites

- **Python 3.11+**
- **Node.js 16+**
- **npm or yarn**
- **OpenAI API Key**
- **Tavily API Key** (optional, for web search)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/multi-agent-advisor.git
cd multi-agent-advisor
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install
```

### 4. Environment Configuration

Create a `.env` file in the root directory:

```env
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional (for web search functionality)
TAVILY_API_KEY=your_tavily_api_key_here

# LangChain Tracing (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langchain_api_key_here
LANGCHAIN_PROJECT=multi-agent-advisor
```

### 5. Quick Setup Script

For Windows:

```bash
./setup.bat
```

For Linux/Mac:

```bash
./setup.sh
```

## 🎯 Usage

### 1. Start the Backend Server

```bash
cd backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Start the Frontend Development Server

```bash
cd frontend
npm start
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### 4. Using the Application

1. **Enter your startup idea** in the text area
2. **Click "Analyze Idea"** to start the evaluation
3. **Review the comprehensive analysis** including:
   - Market research verdict
   - Financial analysis
   - Product strategy assessment
   - Final recommendation with confidence score

## 📚 API Documentation

### Endpoints

#### `POST /evaluate`

Evaluates a startup idea using multiple AI agents.

**Request Body:**

```json
{
  "idea": "Your startup idea description here"
}
```

**Response:**

```json
{
  "market_verdict": "The market analysis demonstrates growing demand...",
  "financial_verdict": "The financial analysis indicates robust projections...",
  "product_verdict": "The product strategy shows well-defined value...",
  "final_recommendation": "launch",
  "rationale": "The combination of favorable market landscape...",
  "confidence_score": 9
}
```

## 📁 Project Structure

```
multi-agent-advisor/
├── backend/
│   ├── main.py                 # FastAPI application entry point
│   ├── requirements.txt        # Python dependencies
│   ├── agents/                 # AI agent definitions
│   │   ├── market_research_agent.py
│   │   ├── financial_advisor_agent.py
│   │   ├── product_strategist_agent.py
│   │   └── summary_agent.py
│   ├── tasks/                  # Agent task definitions
│   │   ├── market_research_task.py
│   │   ├── financial_advisor_task.py
│   │   ├── product_strategy_task.py
│   │   └── summary_task.py
│   ├── tools/                  # Custom tools for agents
│   │   ├── search_tool.py
│   │   └── calculator_tool.py
│   ├── api/                    # API endpoints
│   │   └── evaluate_startup.py
│   ├── langgraph/              # Workflow definitions
│   │   └── advisor_graph.py
│   ├── crew/                   # CrewAI configurations
│   │   └── startup_crew.py
│   └── utils/                  # Utility functions
│       └── sanitizer.py
├── frontend/
│   ├── public/
│   │   ├── index.html
│   │   └── manifest.json
│   ├── src/
│   │   ├── App.js              # Main React component
│   │   ├── index.js            # React entry point
│   │   └── index.css           # Styling
│   ├── package.json            # Node.js dependencies
│   └── README.md
├── .env                        # Environment variables
├── .gitignore
├── setup.bat                   # Windows setup script
├── setup.sh                    # Linux/Mac setup script
└── README.md
```

## ⚙️ Configuration

### Agent Configuration

Each agent can be customized in their respective files:

```python
def create_market_research_agent():
    return Agent(
        role="Market Research Agent",
        goal="Analyze market trends and competition",
        backstory="Experienced market analyst...",
        max_iter=2,                    # Limit iterations for speed
        max_execution_time=15,         # Timeout in seconds
        output_json={...}              # Structured output format
    )
```

### Performance Tuning

- **Parallel Processing**: Agents run concurrently for faster results
- **Timeouts**: Each agent has execution time limits
- **Model Selection**: Use GPT-3.5-turbo for faster responses
- **Caching**: Implement response caching for repeated queries

### CORS Configuration

The backend is configured to allow requests from the React frontend:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 🔧 Development

### Adding New Agents

1. Create agent file in `backend/agents/`
2. Create corresponding task in `backend/tasks/`
3. Update workflow in `backend/langgraph/advisor_graph.py`
4. Add agent to crew configuration

### Customizing the UI

- Modify `frontend/src/App.js` for functionality
- Update `frontend/src/index.css` for styling
- Colors and themes can be adjusted in CSS variables

### Environment Variables

| Variable               | Description                   | Required |
| ---------------------- | ----------------------------- | -------- |
| `OPENAI_API_KEY`       | OpenAI API key for GPT models | Yes      |
| `TAVILY_API_KEY`       | Tavily search API key         | No       |
| `LANGCHAIN_TRACING_V2` | Enable LangChain tracing      | No       |
| `LANGCHAIN_API_KEY`    | LangChain API key             | No       |

## 🚀 Deployment

### Backend Deployment

```bash
# Install production dependencies
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

### Frontend Deployment

```bash
# Build for production
npm run build

# Serve static files
npm install -g serve
serve -s build
```

### Docker Deployment

Create `Dockerfile` for containerized deployment:

```dockerfile
# Backend Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code
- Use meaningful commit messages
- Add tests for new features
- Update documentation as needed

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **CrewAI** for the multi-agent framework
- **LangChain** for LLM integration
- **OpenAI** for GPT models
- **FastAPI** for the web framework
- **React** for the frontend framework

## 🔮 Roadmap

- [ ] Add more specialized agents (Legal, Marketing, etc.)
- [ ] Implement user authentication
- [ ] Add report export functionality
- [ ] Create mobile app version
- [ ] Add integration with business plan templates
- [ ] Implement A/B testing for recommendations

---

**Made with ❤️ by dev-nitya**

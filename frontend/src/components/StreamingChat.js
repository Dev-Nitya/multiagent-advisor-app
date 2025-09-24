import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Link } from 'react-router-dom';
import authService from '../services/authService';
import './StreamingChat.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const StreamingChat = () => {
  const { user, logout } = useAuth();
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentRequestId, setCurrentRequestId] = useState(null);
  const [eventSource, setEventSource] = useState(null);
  const [agentStates, setAgentStates] = useState({});
  const [currentAgent, setCurrentAgent] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Cleanup event source on unmount
  useEffect(() => {
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [eventSource]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isStreaming) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputValue.trim(),
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsStreaming(true);

    try {
      const response = await authService.makeAuthenticatedRequest('/api/evaluate-startup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          idea: userMessage.content,
          stream: true 
        }),
      });

      const data = await response.json();
      
      if (data.request_id) {
        setCurrentRequestId(data.request_id);
        startEventStream(data.request_id);
      } else {
        throw new Error('No request ID received');
      }
    } catch (error) {
      console.error('Error submitting message:', error);
      setMessages(prev => [...prev, {
        id: Date.now(),
        type: 'system',
        content: 'Sorry, there was an error processing your request. Please try again.',
        timestamp: new Date().toISOString(),
        isError: true
      }]);
      setIsStreaming(false);
    }
  };

  const startEventStream = (requestId) => {
    if (eventSource) {
      eventSource.close();
    }

    setAgentStates({});
    setCurrentAgent(null);

    const newEventSource = new EventSource(`${API_BASE_URL}/events/${requestId}`);
    setEventSource(newEventSource);

    // Add initial system message for analysis start
    setMessages(prev => [...prev, {
      id: `${requestId}_start`,
      type: 'system',
      content: '🤖 AI agents are analyzing your idea...',
      timestamp: new Date().toISOString(),
      isProcessing: true
    }]);

    newEventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received SSE event:', data);
        
        handleStreamEvent(data, requestId);
      } catch (error) {
        console.error('Error parsing SSE event:', error);
      }
    };

    newEventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      setEventSource(null);
      setIsStreaming(false);
      
      setMessages(prev => [...prev, {
        id: `${requestId}_error`,
        type: 'system',
        content: 'Connection lost. The analysis may still be in progress.',
        timestamp: new Date().toISOString(),
        isError: true
      }]);
    };

    newEventSource.addEventListener('close', () => {
      console.log('SSE connection closed');
      setEventSource(null);
      setIsStreaming(false);
    });
  };

  const handleStreamEvent = (data, requestId) => {
    switch (data.type) {
      case 'agent_started':
        setCurrentAgent({
          name: data.agent,
          status: 'thinking',
          invocation_id: data.invocation_id
        });
        
        setMessages(prev => [...prev, {
          id: `${data.invocation_id}_started`,
          type: 'agent_status',
          content: `🧠 ${data.agent} is analyzing...`,
          timestamp: new Date(data.ts || Date.now()).toISOString(),
          agent: data.agent,
          status: 'thinking'
        }]);
        break;

      case 'agent_finished':
        setAgentStates(prev => ({
          ...prev,
          [data.agent]: 'finished'
        }));

        if (data.result) {
          // Parse the result and create a structured message
          const parsedResult = parseAgentResult(data.result, data.agent);
          
          setMessages(prev => [...prev, {
            id: `${data.invocation_id}_result`,
            type: 'agent_result',
            content: parsedResult,
            timestamp: new Date(data.ts || Date.now()).toISOString(),
            agent: data.agent,
            rawResult: data.result
          }]);
        }
        break;

      case 'analysis_complete':
        setIsStreaming(false);
        setCurrentAgent(null);
        
        // Remove the processing message
        setMessages(prev => prev.filter(msg => !msg.isProcessing));
        
        setMessages(prev => [...prev, {
          id: `${requestId}_complete`,
          type: 'system',
          content: '✅ Analysis complete! All agents have finished their evaluation.',
          timestamp: new Date(data.ts || Date.now()).toISOString()
        }]);
        break;

      case 'error':
        setIsStreaming(false);
        setCurrentAgent(null);
        
        setMessages(prev => [...prev, {
          id: `${requestId}_error_${Date.now()}`,
          type: 'system',
          content: `❌ Error: ${data.message || 'An unexpected error occurred'}`,
          timestamp: new Date(data.ts || Date.now()).toISOString(),
          isError: true
        }]);
        break;

      default:
        console.log('Unknown event type:', data.type);
    }
  };

  const parseAgentResult = (result, agentName) => {
    try {
      // Try to parse as JSON first
      const parsed = JSON.parse(result);
      
      return {
        agent: agentName,
        summary: parsed.summary,
        verdict: parsed.verdict,
        viability_score: parsed.viability_score,
        confidence_score: parsed.confidence_score,
        final_recommendation: parsed.final_recommendation,
        rationale: parsed.rationale,
        raw: result
      };
    } catch (e) {
      // If not JSON, try to extract structured data with regex
      const extractStructuredData = (text) => {
        const extracted = {
          summary: null,
          verdict: null,
          viability_score: null,
          confidence_score: null,
          raw: text
        };

        // Extract summary
        const summaryMatch = text.match(/"summary":\s*"([^"]+)"/);
        if (summaryMatch) {
          extracted.summary = summaryMatch[1];
        }

        // Extract verdict
        const verdictMatch = text.match(/"verdict":\s*"([^"]+)"/);
        if (verdictMatch) {
          extracted.verdict = verdictMatch[1];
        }

        // Extract viability_score
        const scoreMatch = text.match(/"viability_score":\s*"?(\d+(?:\.\d+)?)"?/);
        if (scoreMatch) {
          extracted.viability_score = parseFloat(scoreMatch[1]);
        }

        // Extract confidence_score
        const confidenceMatch = text.match(/"confidence_score":\s*"?(\d+(?:\.\d+)?)"?/);
        if (confidenceMatch) {
          extracted.confidence_score = parseFloat(confidenceMatch[1]);
        }

        // If no structured data found, put everything in summary
        if (!extracted.summary && !extracted.verdict && extracted.viability_score === null) {
          extracted.summary = text;
        }

        return extracted;
      };

      const structuredData = extractStructuredData(result);
      return {
        agent: agentName,
        ...structuredData
      };
    }
  };

  const getAgentIcon = (agentName) => {
    const icons = {
      'Market Research Agent': '📊',
      'Financial Advisor': '💰',
      'Product Strategy Agent': '📦',
      'Summary Agent': '📝'
    };
    return icons[agentName] || '🤖';
  };

  const getVerdictColor = (verdict) => {
    if (!verdict) return '#6b7280';
    const v = verdict.toLowerCase();
    if (v.includes('viable') && !v.includes('not')) return '#10b981';
    if (v.includes('not') && v.includes('viable')) return '#ef4444';
    return '#f59e0b';
  };

  const renderMessage = (message) => {
    if (message.type === 'user') {
      return (
        <div key={message.id} className="message user-message">
          <div className="message-content">
            <div className="message-text">{message.content}</div>
            <div className="message-time">
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          </div>
        </div>
      );
    }

    if (message.type === 'system') {
      return (
        <div key={message.id} className={`message system-message ${message.isError ? 'error' : ''} ${message.isProcessing ? 'processing' : ''}`}>
          <div className="message-content">
            <div className="message-text">{message.content}</div>
            <div className="message-time">
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          </div>
        </div>
      );
    }

    if (message.type === 'agent_status') {
      return (
        <div key={message.id} className="message agent-status-message">
          <div className="message-content">
            <div className="agent-status">
              {getAgentIcon(message.agent)} {message.content}
              {message.status === 'thinking' && <div className="thinking-dots">...</div>}
            </div>
            <div className="message-time">
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          </div>
        </div>
      );
    }

    if (message.type === 'agent_result') {
      const result = message.content;
      return (
        <div key={message.id} className="message agent-result-message">
          <div className="message-content">
            <div className="agent-header">
              <span className="agent-icon">{getAgentIcon(message.agent)}</span>
              <span className="agent-name">{message.agent}</span>
            </div>
            
            <div className="agent-result">
              {result.summary && (
                <div className="result-section">
                  <strong>📋 Analysis:</strong>
                  <p>{result.summary}</p>
                </div>
              )}
              
              {result.verdict && (
                <div className="result-section">
                  <strong>🎯 Verdict:</strong>
                  <span 
                    className="verdict-badge"
                    style={{ color: getVerdictColor(result.verdict) }}
                  >
                    {result.verdict}
                  </span>
                </div>
              )}
              
              {result.viability_score !== null && result.viability_score !== undefined && (
                <div className="result-section">
                  <strong>📊 Viability Score:</strong>
                  <div className="score-display">
                    <span className="score-value">{result.viability_score}/10</span>
                    <div className="score-bar">
                      <div 
                        className="score-fill" 
                        style={{ width: `${(result.viability_score / 10) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              )}

              {result.final_recommendation && (
                <div className="result-section">
                  <strong>🎯 Final Recommendation:</strong>
                  <div className="final-recommendation">
                    {result.final_recommendation}
                  </div>
                  {result.rationale && (
                    <p className="rationale">{result.rationale}</p>
                  )}
                </div>
              )}

              {result.confidence_score !== null && result.confidence_score !== undefined && (
                <div className="result-section">
                  <strong>🎯 Confidence:</strong>
                  <span className="confidence-score">{result.confidence_score}/10</span>
                </div>
              )}
            </div>
            
            <div className="message-time">
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="streaming-chat">
      <div className="chat-header">
        <div className="header-top">
          <div className="header-title">
            <h1>💡 AI Startup Advisor</h1>
            <p>Chat with our AI agents to evaluate your startup idea</p>
          </div>
          <div className="header-controls">
            <div className="user-info">
              <span className="user-name">👋 {user?.full_name || user?.email}</span>
            </div>
            <div className="nav-links">
              <Link to="/prompts" className="nav-link">📝 Prompts</Link>
              <Link to="/cost-dashboard" className="nav-link">💰 Costs</Link>
              {user?.tier === 'ENTERPRISE' && (
                <Link to="/admin" className="nav-link">⚙️ Admin</Link>
              )}
            </div>
            <button onClick={logout} className="logout-btn">Logout</button>
          </div>
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <h2>Welcome to AI Startup Advisor! 👋</h2>
            <p>Describe your startup idea and our AI agents will provide comprehensive analysis including:</p>
            <ul>
              <li>📊 Market research and opportunities</li>
              <li>💰 Financial viability assessment</li>
              <li>📦 Product strategy recommendations</li>
              <li>📝 Overall summary and verdict</li>
            </ul>
            <p>Type your startup idea below to get started!</p>
          </div>
        )}
        
        {messages.map(renderMessage)}
        
        {currentAgent && (
          <div className="current-agent-indicator">
            <div className="agent-thinking">
              {getAgentIcon(currentAgent.name)} {currentAgent.name} is thinking...
              <div className="thinking-animation"></div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="chat-input-form">
        <div className="input-container">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Describe your startup idea..."
            disabled={isStreaming}
            className="chat-input"
          />
          <button 
            type="submit" 
            disabled={!inputValue.trim() || isStreaming}
            className="send-button"
          >
            {isStreaming ? '⏳' : '🚀'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default StreamingChat;

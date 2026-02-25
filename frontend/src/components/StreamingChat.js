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
      console.error('🚨 SSE connection error:', error);
      console.log('EventSource readyState:', newEventSource.readyState);
      console.log('EventSource url:', newEventSource.url);
      
      // Only show error message if the connection failed unexpectedly
      // (readyState 2 = CLOSED is normal after completion)
      if (newEventSource.readyState !== EventSource.CLOSED || isStreaming) {
        setEventSource(null);
        setIsStreaming(false);
        
        setMessages(prev => [...prev, {
          id: `${requestId}_error`,
          type: 'system',
          content: 'Connection lost. The analysis may still be in progress.',
          timestamp: new Date().toISOString(),
          isError: true
        }]);
      }
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

        console.log('✅ Agent finished:', data);
        if (data.result || data.result_snippet) {
          console.log('✅ Agent result received for:', data.agent);
          // Parse the result and create a structured message
          const resultData = data.result || data.result_snippet;
          const parsedResult = parseAgentResult(resultData, data.agent);
          
          setMessages(prev => [...prev, {
            id: `${data.invocation_id}_result`,
            type: 'agent_result',
            content: parsedResult,
            timestamp: new Date(data.ts || Date.now()).toISOString(),
            agent: data.agent,
            rawResult: resultData
          }]);
        }
        break;

      case 'analysis_complete':
      case 'complete':
        console.log('🏁 Analysis complete event received');
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
        
        // Close the EventSource connection after completion
        if (eventSource) {
          console.log('🔌 Closing EventSource connection after completion');
          eventSource.close();
          setEventSource(null);
        }
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
        console.log('❓ Unknown event type:', data.type, 'Data:', data);
    }
  };

  const parseAgentResult = (result, agentName) => {
      console.log('🔍 Parsing result for agent:', agentName);
      console.log('📄 Raw result:', result);
      
      // Check if this is a Product Strategy Agent to add specific debugging
      const isProductAgent = agentName.toLowerCase().includes('product') || agentName.toLowerCase().includes('strategist');
      
    try {
      // Try to parse as JSON first
      const parsed = JSON.parse(result);
      console.log('✅ Parsed JSON:', parsed);
      console.log('✅ JSON Parse successful for agent:', agentName);
      
      // Handle Summary Agent's different output format
      if (agentName === 'Summary Agent' || agentName.toLowerCase().includes('summary')) {
        console.log('🔍 Summary Agent detected, agent name:', agentName);
        console.log('🔍 Summary Agent parsed data:', parsed);
        const summaryResult = {
          agent: agentName,
          isSummaryAgent: true,
          market_verdict: parsed.market_verdict,
          financial_verdict: parsed.financial_verdict,
          product_verdict: parsed.product_verdict,
          final_recommendation: parsed.final_recommendation,
          rationale: parsed.rationale,
          confidence_score: parsed.confidence_score,
          raw: result
        };
        console.log('📝 Summary Agent result created:', summaryResult);
        return summaryResult;
      }
      
      // Handle other agents' format
      // Check if product strategy fields are nested under product_strategy
      const productStrategy = parsed.product_strategy || {};
      
      if (isProductAgent) {
        console.log('🔍 Product strategy data (nested):', productStrategy);
        console.log('🔍 Direct fields on parsed object (legacy):', {
          user_personas: parsed.user_personas,
          must_have_features: parsed.must_have_features,
          MVP_scope: parsed.MVP_scope,
          GTM_strategy: parsed.GTM_strategy
        });
        console.log('🔍 Structure detected:', productStrategy.user_personas ? 'NESTED' : 'FLAT');
      }
      
      // Extract fields with fallback logic for both flat and nested structures
      // Primary expectation: Nested under product_strategy (current backend format)
      // Fallback: Flat structure (legacy support)
      const extractedFields = {
        user_personas: productStrategy.user_personas || parsed.user_personas,
        must_have_features: productStrategy.must_have_features || parsed.must_have_features,
        MVP_scope: productStrategy.MVP_scope || parsed.MVP_scope,
        GTM_strategy: productStrategy.GTM_strategy || parsed.GTM_strategy
      };
      
      if (isProductAgent) {
        console.log('🔧 Final extracted product strategy fields:', extractedFields);
      }
      
      return {
        agent: agentName,
        summary: parsed.summary,
        verdict: parsed.verdict,
        viability_score: parsed.viability_score,
        confidence_score: parsed.confidence_score,
        // Support both flat structure and nested under product_strategy
        user_personas: extractedFields.user_personas,
        must_have_features: extractedFields.must_have_features,
        MVP_scope: extractedFields.MVP_scope,
        GTM_strategy: extractedFields.GTM_strategy,
        raw: result
      };
    } catch (e) {
      console.error('❌ JSON parsing failed for agent:', agentName);
      console.error('❌ Error details:', e);
      console.error('❌ Raw result that failed to parse:', result);
      // If not JSON, return as raw text
      return {
        agent: agentName,
        summary: result,
        raw: result,
        parseError: true
      };
    }
  };

  const getAgentIcon = (agentName) => {
    const icons = {
      'Market Research Agent': '📊',
      'Financial Advisor': '💰',
      'Product Strategy Agent': '📦',
      'product_strategist': '📦',  // Handle lowercase variant
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
      console.log('🎨 Rendering agent result for:', message.agent);
      console.log('📊 Result content:', result);
      
      // Debug Product Strategy fields specifically
      if (message.agent.toLowerCase().includes('product') || message.agent.toLowerCase().includes('strategist')) {
        console.log('🔍 Product Strategy Rendering Debug:');
        console.log('  - user_personas:', result.user_personas);
        console.log('  - must_have_features:', result.must_have_features);
        console.log('  - MVP_scope:', result.MVP_scope);
        console.log('  - GTM_strategy:', result.GTM_strategy);
      }
      
      return (
        <div key={message.id} className="message agent-result-message">
          <div className="message-content">
            <div className="agent-header">
              <span className="agent-icon">{getAgentIcon(message.agent)}</span>
              <span className="agent-name">{message.agent}</span>
            </div>
            
            <div className="agent-result">
              {/* Summary Agent specific rendering */}
              {result.isSummaryAgent ? (
                <div className="summary-agent-result">
                  {result.market_verdict && (
                    <div className="result-section">
                      <strong>📊 Market Analysis:</strong>
                      <p>{result.market_verdict}</p>
                    </div>
                  )}
                  {result.financial_verdict && (
                    <div className="result-section">
                      <strong>💰 Financial Analysis:</strong>
                      <p>{result.financial_verdict}</p>
                    </div>
                  )}
                  {result.product_verdict && (
                    <div className="result-section">
                      <strong>📦 Product Analysis:</strong>
                      <p>{result.product_verdict}</p>
                    </div>
                  )}
                  {result.final_recommendation && (
                    <div className="result-section">
                      <strong>🎯 Final Recommendation:</strong>
                      <div className="final-recommendation" style={{ 
                        fontWeight: 'bold', 
                        color: result.final_recommendation === 'launch' ? '#10b981' : 
                               result.final_recommendation === 'iterate' ? '#f59e0b' : '#ef4444',
                        textTransform: 'uppercase',
                        fontSize: '1.1em'
                      }}>
                        {result.final_recommendation}
                      </div>
                      {result.rationale && (
                        <p className="rationale" style={{ marginTop: '8px', fontStyle: 'italic' }}>
                          {result.rationale}
                        </p>
                      )}
                    </div>
                  )}
                  {result.confidence_score && (
                    <div className="result-section">
                      <strong>🎯 Confidence:</strong>
                      <span className="confidence-score">{result.confidence_score}/10</span>
                    </div>
                  )}
                </div>
              ) : (
                /* Other agents rendering */
                <>
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

                  {result.confidence_score !== null && result.confidence_score !== undefined && (
                    <div className="result-section">
                      <strong>🎯 Confidence:</strong>
                      <span className="confidence-score">{result.confidence_score}/10</span>
                    </div>
                  )}

                  {/* Product Strategist specific fields */}
                  {result.user_personas && result.user_personas.length > 0 && (
                    <div className="result-section">
                      <strong>👥 User Personas:</strong>
                      <div className="personas-list">
                        {result.user_personas.map((persona, index) => (
                          <div key={index} className="persona-item">
                            <h4 className="persona-name">{persona.name}</h4>
                            <p className="persona-description">{persona.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {result.must_have_features && result.must_have_features.length > 0 && (
                    <div className="result-section">
                      <strong>✅ Must-Have Features:</strong>
                      <ul className="features-list">
                        {result.must_have_features.map((feature, index) => (
                          <li key={index} className="feature-item">{feature}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {result.MVP_scope && (
                    <div className="result-section">
                      <strong>🚀 MVP Scope:</strong>
                      <p>{result.MVP_scope}</p>
                    </div>
                  )}

                  {result.GTM_strategy && (
                    <div className="result-section">
                      <strong>📈 Go-to-Market Strategy:</strong>
                      <p>{result.GTM_strategy}</p>
                    </div>
                  )}

                  {/* Fallback for parse errors or unexpected responses */}
                  {result.parseError && (
                    <div className="result-section">
                      <strong>⚠️ Raw Response:</strong>
                      <pre style={{ background: '#f3f4f6', padding: '10px', borderRadius: '4px', fontSize: '0.8em' }}>
                        {result.raw}
                      </pre>
                    </div>
                  )}
                </>
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

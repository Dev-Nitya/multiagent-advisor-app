import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import Navigation from './Navigation';
import axios from 'axios';
import authService from '../services/authService';
import promptService from '../services/promptService';
import './Dashboard.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const Dashboard = () => {
  const { user, refreshUser } = useAuth();
  const [idea, setIdea] = useState('');
  const [selectedPromptId, setSelectedPromptId] = useState('');
  const [prompts, setPrompts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [updatingSettings, setUpdatingSettings] = useState(false);
  const [promptsLoading, setPromptsLoading] = useState(false);
  
  // New states for real-time streaming
  const [streamingEvents, setStreamingEvents] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentRequestId, setCurrentRequestId] = useState(null);
  const [eventSource, setEventSource] = useState(null);
  const [agentStates, setAgentStates] = useState({}); // Track agent thinking/finished states
  const [groupedEvents, setGroupedEvents] = useState({}); // Group events by invocation_id
  const [agentResults, setAgentResults] = useState({}); // Store results from each agent
  const [analysisComplete, setAnalysisComplete] = useState(false); // Track if analysis is complete
  const [currentAgent, setCurrentAgent] = useState(null); // Current active agent
  
  // New states for agent prompt selection
  const [promptSelectionMode, setPromptSelectionMode] = useState('global'); // 'global' or 'agent'
  const [agentPrompts, setAgentPrompts] = useState({
    market_research: '',
    financial_advisor: '',
    product_strategist: '',
    summary_agent: ''
  });

  // Available agent versions - these will be populated from actual prompts
  const [agentVersions, setAgentVersions] = useState({
    market_research: [],
    financial_advisor: [],
    product_strategist: [],
    summary_agent: []
  });

  useEffect(() => {
    fetchPrompts();
  }, []);

  const fetchPrompts = async () => {
    setPromptsLoading(true);
    try {
      const result = await promptService.getAllPrompts();
      if (result.success) {
        setPrompts(result.data);
        
        // Categorize prompts by agent type
        const categorizedPrompts = {
          market_research: [],
          financial_advisor: [],
          product_strategist: [],
          summary_agent: []
        };

        result.data.forEach(prompt => {
          const name = prompt.name.toLowerCase();
          if (name.includes('market') || name.includes('research')) {
            categorizedPrompts.market_research.push({
              id: prompt.prompt_id,
              name: prompt.name,
              version: prompt.version
            });
          } else if (name.includes('financial') || name.includes('advisor')) {
            categorizedPrompts.financial_advisor.push({
              id: prompt.prompt_id,
              name: prompt.name,
              version: prompt.version
            });
          } else if (name.includes('product') || name.includes('strategist')) {
            categorizedPrompts.product_strategist.push({
              id: prompt.prompt_id,
              name: prompt.name,
              version: prompt.version
            });
          } else if (name.includes('summary')) {
            categorizedPrompts.summary_agent.push({
              id: prompt.prompt_id,
              name: prompt.name,
              version: prompt.version
            });
          }
        });

        setAgentVersions(categorizedPrompts);
        
        // Set the first prompt as default if available
        if (result.data.length > 0) {
          setSelectedPromptId(result.data[0].prompt_id);
        }
      } else {
        console.error('Failed to fetch prompts:', result.error);
      }
    } catch (err) {
      console.error('Error fetching prompts:', err);
    } finally {
      setPromptsLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!idea.trim()) return;

    // Validate prompt selection
    if (!isAgentPromptSelectionValid()) {
      setError({
        message: 'Please select at least one agent prompt or switch to global mode.',
        type: 'validation'
      });
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setAnalysisComplete(false);
    setAgentResults({});
    setCurrentAgent(null);

    try {
      const requestId = `req-${Date.now()}`;
      const requestData = {
        idea: idea.trim(),
        user_id: user.user_id,
        request_id: requestId
      };
      
      // Add prompt data based on selection mode
      if (promptSelectionMode === 'global' && selectedPromptId) {
        requestData.global_prompt_id = selectedPromptId;
      } else if (promptSelectionMode === 'agent') {
        // Only include non-empty agent prompts
        const validAgentPrompts = {};
        Object.entries(agentPrompts).forEach(([key, value]) => {
          if (value) {
            validAgentPrompts[key] = value;
          }
        });
        
        if (Object.keys(validAgentPrompts).length > 0) {
          requestData.agent_prompt_ids = validAgentPrompts;
        }
      }

      // Start streaming events before making the API call
      startEventStream(requestId);

      // Make the API call (this will start background processing)
      const response = await axios.post(`${API_BASE_URL}/evaluate`, requestData);
      
      // Use the request_id from response if provided, otherwise use our generated one
      const actualRequestId = response.data?.request_id || requestId;
      
      // If the backend returned a different request_id, restart streaming with correct ID
      if (actualRequestId !== requestId) {
        startEventStream(actualRequestId);
      }
      
      console.log('Evaluation started:', response.data);
      
      // Add initial event to show evaluation started
      setStreamingEvents(prev => [...prev, {
        type: 'info',
        message: 'Evaluation started, processing your startup idea...',
        timestamp: new Date().toISOString(),
        id: `init_${Date.now()}`
      }]);

      // Refresh user profile to update budget usage
      await refreshUser();

    } catch (err) {
      // Stop streaming on error
      stopEventStream();
      
      let errorMessage = 'An error occurred while evaluating your startup idea.';
      let errorType = 'general';
      
      if (err.response?.data) {
        if (typeof err.response.data.detail === 'string') {
          errorMessage = err.response.data.detail;
          
          // Detect prompt injection error
          if (errorMessage.toLowerCase().includes('prompt injection detected')) {
            errorType = 'prompt_injection';
            errorMessage = '🛡️ Security Alert: Your idea contains potentially harmful content that has been blocked by our security filters. Please rephrase your idea and try again.';
          }
        } else if (Array.isArray(err.response.data.detail)) {
          errorMessage = err.response.data.detail.map(error => 
            `${error.loc?.join(' ')}: ${error.msg}`
          ).join(', ');
        } else if (err.response.data.message) {
          errorMessage = err.response.data.message;
        }
      }
      
      setError({ message: errorMessage, type: errorType });
    } finally {
      setLoading(false);
    }
  };

  const handlePromptSanitizationToggle = async (e) => {
    const enabled = e.target.checked;
    setUpdatingSettings(true);

    try {
      const result = await authService.updatePromptSanitization(enabled);
      if (result.success) {
        // Refresh user data to reflect the change
        await refreshUser();
      } else {
        setError({ message: result.error || 'Failed to update prompt sanitization setting', type: 'general' });
        // Revert the toggle
        e.target.checked = !enabled;
      }
    } catch (err) {
      setError({ message: 'An error occurred while updating settings', type: 'general' });
      // Revert the toggle
      e.target.checked = !enabled;
    } finally {
      setUpdatingSettings(false);
    }
  };

  const getRecommendationStyle = (recommendation) => {
    switch (recommendation?.toLowerCase()) {
      case 'go':
      case 'launch':
        return 'verdict viable';
      case 'no-go':
      case 'abandon':
        return 'verdict not-viable';
      case 'pivot':
      case 'iterate':
      case 'uncertain':
        return 'verdict uncertain';
      default:
        return 'verdict uncertain';
    }
  };

  const getConfidenceColor = (score) => {
    if (score >= 0.8) return '#4ade80'; // Green
    if (score >= 0.6) return '#fbbf24'; // Yellow
    if (score >= 0.4) return '#fb923c'; // Orange
    return '#f87171'; // Red
  };

  const getStreamingPreview = (agentName, resultSnippet) => {
    try {
      const parsed = JSON.parse(resultSnippet);
      
      // Extract key information for preview
      if (parsed.verdict) {
        return `Verdict: ${parsed.verdict}`;
      }
      if (parsed.final_recommendation) {
        return `Recommends: ${parsed.final_recommendation}`;
      }
      if (parsed.summary) {
        // Get first 50 characters of summary
        return parsed.summary.substring(0, 50).trim() + '...';
      }
      if (parsed.viability_score !== undefined) {
        return `Score: ${parsed.viability_score}/10`;
      }
      
      return 'Analysis complete';
    } catch (e) {
      // If not JSON, show first few words of raw text
      const words = resultSnippet.split(' ').slice(0, 8).join(' ');
      return words.length > 50 ? words.substring(0, 50).trim() + '...' : words + '...';
    }
  };

  const getTierColor = (tier) => {
    switch (tier?.toLowerCase()) {
      case 'premium':
        return '#fbbf24';
      case 'enterprise':
        return '#a855f7';
      default:
        return '#808080';
    }
  };

  const getBudgetUsagePercentage = (spent, limit) => {
    return limit > 0 ? (spent / limit) * 100 : 0;
  };

  const getBudgetColor = (percentage) => {
    if (percentage < 70) return '#4ade80';
    if (percentage < 90) return '#fbbf24';
    return '#ef4444';
  };

  // Helper functions for agent prompt management
  const handlePromptSelectionModeChange = (mode) => {
    setPromptSelectionMode(mode);
    if (mode === 'global') {
      // Clear agent prompts when switching to global
      setAgentPrompts({
        market_research: '',
        financial_advisor: '',
        product_strategist: '',
        summary_agent: ''
      });
    } else {
      // Clear global prompt when switching to agent mode
      setSelectedPromptId('');
    }
  };

  const handleAgentPromptChange = (agentKey, promptId) => {
    setAgentPrompts(prev => ({
      ...prev,
      [agentKey]: promptId
    }));
  };

  const getAgentDisplayName = (agentKey) => {
    const names = {
      market_research: 'Market Research',
      financial_advisor: 'Financial Advisor',
      product_strategist: 'Product Strategist',
      summary_agent: 'Summary'
    };
    return names[agentKey] || agentKey;
  };

  const isAgentPromptSelectionValid = () => {
    if (promptSelectionMode === 'global') {
      return true; // Global mode is always valid (can be empty)
    }
    
    // For agent mode, at least one agent should be selected
    return Object.values(agentPrompts).some(promptId => promptId !== '');
  };

  // Helper function to extract JSON-like data from potentially malformed strings
  const extractStructuredData = (text, agentName) => {
    const extracted = {
      summary: '',
      verdict: '',
      viability_score: null,
      confidence_score: null,
      // Product Strategy fields
      user_personas: null,
      must_have_features: null,
      MVP_scope: null,
      GTM_strategy: null,
      // Summary Agent fields
      isSummaryAgent: false,
      market_verdict: '',
      financial_verdict: '',
      product_verdict: '',
      final_recommendation: '',
      rationale: ''
    };

    try {
      // First try direct JSON parsing
      const parsed = JSON.parse(text);
      
      // Handle Summary Agent's different output format
      if (agentName === 'Summary Agent' || agentName.toLowerCase().includes('summary')) {
        extracted.isSummaryAgent = true;
        extracted.market_verdict = parsed.market_verdict || '';
        extracted.financial_verdict = parsed.financial_verdict || '';
        extracted.product_verdict = parsed.product_verdict || '';
        extracted.final_recommendation = parsed.final_recommendation || '';
        extracted.rationale = parsed.rationale || '';
        extracted.confidence_score = typeof parsed.confidence_score === 'string' 
          ? parseFloat(parsed.confidence_score) 
          : (parsed.confidence_score || 0);
        return extracted;
      }
      
      // Handle other agents
      extracted.summary = parsed.summary || '';
      extracted.verdict = parsed.verdict || '';
      extracted.viability_score = parsed.viability_score || null;
      
      // Ensure confidence_score is a number
      if (parsed.confidence_score !== undefined) {
        extracted.confidence_score = typeof parsed.confidence_score === 'string' 
          ? parseFloat(parsed.confidence_score) 
          : parsed.confidence_score;
      }
      
      // Handle Product Strategy fields (both nested and flat structures)
      const productStrategy = parsed.product_strategy || {};
      extracted.user_personas = productStrategy.user_personas || parsed.user_personas;
      extracted.must_have_features = productStrategy.must_have_features || parsed.must_have_features;
      extracted.MVP_scope = productStrategy.MVP_scope || parsed.MVP_scope;
      extracted.GTM_strategy = productStrategy.GTM_strategy || parsed.GTM_strategy;
      
      return extracted;
    } catch (e) {
      // If direct parsing fails, try to extract using regex patterns
      
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

      // Extract viability_score (handle both quoted and unquoted numbers)
      const scoreMatch = text.match(/"viability_score":\s*"?(\d+(?:\.\d+)?)"?/);
      if (scoreMatch) {
        extracted.viability_score = parseFloat(scoreMatch[1]);
      }

      // Extract confidence_score (handle both quoted and unquoted numbers)
      const confidenceMatch = text.match(/"confidence_score":\s*"?(\d+(?:\.\d+)?)"?/);
      if (confidenceMatch) {
        extracted.confidence_score = parseFloat(confidenceMatch[1]);
      }

      // Extract MVP_scope
      const mvpMatch = text.match(/"MVP_scope":\s*"([^"]+)"/);
      if (mvpMatch) {
        extracted.MVP_scope = mvpMatch[1];
      }

      // Extract GTM_strategy
      const gtmMatch = text.match(/"GTM_strategy":\s*"([^"]+)"/);
      if (gtmMatch) {
        extracted.GTM_strategy = gtmMatch[1];
      }

      // Extract Summary Agent fields (only if agent is Summary Agent)
      if (agentName === 'Summary Agent' || agentName.toLowerCase().includes('summary')) {
        const marketVerdictMatch = text.match(/"market_verdict":\s*"([^"]+)"/);
        if (marketVerdictMatch) {
          extracted.market_verdict = marketVerdictMatch[1];
          extracted.isSummaryAgent = true;
        }
      }

      if (agentName === 'Summary Agent' || agentName.toLowerCase().includes('summary')) {
        const financialVerdictMatch = text.match(/"financial_verdict":\s*"([^"]+)"/);
        if (financialVerdictMatch) {
          extracted.financial_verdict = financialVerdictMatch[1];
          extracted.isSummaryAgent = true;
        }

        const productVerdictMatch = text.match(/"product_verdict":\s*"([^"]+)"/);
        if (productVerdictMatch) {
          extracted.product_verdict = productVerdictMatch[1];
          extracted.isSummaryAgent = true;
        }

        const finalRecommendationMatch = text.match(/"final_recommendation":\s*"([^"]+)"/);
        if (finalRecommendationMatch) {
          extracted.final_recommendation = finalRecommendationMatch[1];
          extracted.isSummaryAgent = true;
        }

        const rationaleMatch = text.match(/"rationale":\s*"([^"]+)"/);
        if (rationaleMatch) {
          extracted.rationale = rationaleMatch[1];
        }
      }

      // If no structured data found, put everything in summary
      if (!extracted.summary && !extracted.verdict && extracted.viability_score === null && !extracted.isSummaryAgent) {
        extracted.summary = text;
      }

      return extracted;
    }
  };

  // Helper function to build final result from agent results
  const buildFinalResultFromAgents = (agentResults) => {
    const result = {
      agents: {} // Store individual agent results
    };
    
    // Process each agent result and parse JSON data
    Object.entries(agentResults).forEach(([agentName, resultSnippet]) => {
      const structuredData = extractStructuredData(resultSnippet, agentName);
      
      // Store the structured result for this agent
      result.agents[agentName] = {
        summary: structuredData.summary,
        verdict: structuredData.verdict,
        viability_score: structuredData.viability_score,
        confidence_score: structuredData.confidence_score,
        // Product Strategy fields
        user_personas: structuredData.user_personas,
        must_have_features: structuredData.must_have_features,
        MVP_scope: structuredData.MVP_scope,
        GTM_strategy: structuredData.GTM_strategy,
        // Summary Agent fields
        isSummaryAgent: structuredData.isSummaryAgent,
        market_verdict: structuredData.market_verdict,
        financial_verdict: structuredData.financial_verdict,
        product_verdict: structuredData.product_verdict,
        final_recommendation: structuredData.final_recommendation,
        rationale: structuredData.rationale,
        raw: resultSnippet
      };

      // Legacy fields for backward compatibility
      const agentMapping = {
        'Market Research Agent': 'market_verdict',
        'Financial Advisor': 'financial_verdict', 
        'Product Strategy Agent': 'product_verdict',
        'Summary Agent': 'final_recommendation'
      };
      
      const resultField = agentMapping[agentName];
      if (resultField && agentName !== 'Summary Agent') {
        result[resultField] = structuredData.summary || resultSnippet;
      } else if (agentName === 'Summary Agent') {
        result[resultField] = structuredData.final_recommendation || resultSnippet;
      }

      // If this is the Summary Agent, extract overall recommendation
      if (agentName === 'Summary Agent') {
        try {
          const parsed = JSON.parse(resultSnippet);
          if (parsed.final_recommendation) {
            result.final_recommendation = parsed.final_recommendation;
          }
          if (parsed.rationale) {
            result.rationale = parsed.rationale;
          }
          if (parsed.confidence_score !== undefined) {
            // Ensure confidence_score is a number
            result.confidence_score = typeof parsed.confidence_score === 'string' 
              ? parseFloat(parsed.confidence_score) 
              : parsed.confidence_score;
          }
        } catch (e) {
          // If Summary Agent doesn't have structured data, that's ok
        }
      }
    });

    return result;
  };

  // Function to start streaming events
  const startEventStream = (requestId) => {
    if (eventSource) {
      eventSource.close();
    }

    setStreamingEvents([]);
    setIsStreaming(true);
    setCurrentRequestId(requestId);
    setAgentStates({});
    setGroupedEvents({});
    setAgentResults({});
    setAnalysisComplete(false);
    setCurrentAgent(null);

    const newEventSource = new EventSource(`${API_BASE_URL}/events/${requestId}`);
    setEventSource(newEventSource);

    // Track if we've received a complete event to avoid showing connection errors
    let hasReceivedComplete = false;

    newEventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received SSE event:', data);
        
        // Generate unique key for grouping/deduplication
        const groupKey = data.invocation_id || `${requestId}_${data.agent || 'unknown'}`;
        
        // Update grouped events for deduplication
        setGroupedEvents(prev => ({
          ...prev,
          [groupKey]: {
            ...prev[groupKey],
            ...data,
            timestamp: data.ts || Date.now()
          }
        }));

        // Handle different event types
        switch (data.type) {
          case 'agent_started':
            setCurrentAgent({
              name: data.agent,
              status: 'thinking',
              invocation_id: data.invocation_id,
              graph_node: data.graph_node,
              started_at: data.ts
            });

            // Track that this agent has started
            setAgentStates(prev => ({
              ...prev,
              [data.agent]: 'thinking'
            }));
            
            setStreamingEvents(prev => [...prev, {
              id: `${groupKey}_started_${Date.now()}`,
              type: 'info',
              message: `🤖 ${data.agent} is analyzing your idea...`,
              timestamp: new Date(data.ts || Date.now()).toISOString(),
              agent: data.agent,
              invocation_id: data.invocation_id
            }]);
            break;

          case 'agent_finished':
            // Mark agent as finished
            setAgentStates(prev => ({
              ...prev,
              [data.agent]: 'finished'
            }));

            setCurrentAgent(prev => prev && prev.name === data.agent ? {
              ...prev,
              status: 'finished',
              result_snippet: data.result_snippet,
              finished_at: data.ts
            } : prev);

            // Capture the agent result for building final analysis
            if (data.result_snippet) {
              setAgentResults(prev => ({
                ...prev,
                [data.agent]: data.result_snippet
              }));
            }
            
            setStreamingEvents(prev => [...prev, {
              id: `${groupKey}_finished_${Date.now()}`,
              type: 'success',
              message: `✅ ${data.agent} completed analysis`,
              timestamp: new Date(data.ts || Date.now()).toISOString(),
              agent: data.agent,
              invocation_id: data.invocation_id,
              result_snippet: data.result_snippet
            }]);
            break;

          case 'error':
            setStreamingEvents(prev => [...prev, {
              id: `error_${Date.now()}`,
              type: 'error',
              message: `❌ Error: ${data.message || 'Unknown error occurred'}`,
              timestamp: new Date(data.ts || Date.now()).toISOString(),
              agent: data.agent,
              invocation_id: data.invocation_id
            }]);
            break;

          default:
            // Handle any other event types
            setStreamingEvents(prev => [...prev, {
              id: `${data.type}_${Date.now()}`,
              type: 'info',
              message: data.message || `${data.type} event received`,
              timestamp: new Date(data.ts || Date.now()).toISOString(),
              agent: data.agent,
              invocation_id: data.invocation_id
            }]);
        }
      } catch (error) {
        console.error('Error parsing SSE event:', error);
        setStreamingEvents(prev => [...prev, {
          id: `parse_error_${Date.now()}`,
          type: 'error',
          message: '⚠️ Received malformed event data',
          timestamp: new Date().toISOString()
        }]);
      }
    };

    newEventSource.onerror = (error) => {
      // Only log error if we haven't received complete event (expected closure)
      if (!hasReceivedComplete) {
        console.error('🚨 EventSource error:', error);
      } else {
        console.log('✅ EventSource closed after completion (expected)');
      }
      
      // Only show connection error if we haven't received a complete event
      if (!hasReceivedComplete && newEventSource.readyState !== EventSource.CLOSED) {
        setStreamingEvents(prev => [...prev, {
          id: `connection_error_${Date.now()}`,
          type: 'error',
          message: '🔄 Connection interrupted, retrying...',
          timestamp: new Date().toISOString()
        }]);
      }
      
      // EventSource will automatically retry, but stop after too many failures
      setTimeout(() => {
        if (newEventSource.readyState === EventSource.CLOSED && !hasReceivedComplete) {
          stopEventStream();
        }
      }, 5000);
    };

    newEventSource.onopen = () => {
      console.log('EventSource connection opened');
      setStreamingEvents(prev => [...prev, {
        id: `connection_open_${Date.now()}`,
        type: 'info',
        message: '🔗 Connected to live updates',
        timestamp: new Date().toISOString()
      }]);
    };

    // Listen for the special 'complete' event type
    newEventSource.addEventListener('complete', (event) => {
      console.log('Received complete event:', event);
      hasReceivedComplete = true; // Mark that we've received completion
      
      try {
        const data = JSON.parse(event.data);
        console.log('Complete event data:', data);
        
        // Use a timeout to ensure all agent results are captured
        setTimeout(() => {
          setAgentResults(currentResults => {
            console.log('Building final result from:', currentResults);
            const finalResult = buildFinalResultFromAgents(currentResults);
            setResult(finalResult);
            setAnalysisComplete(true);
            setCurrentAgent(null);
            
            setStreamingEvents(prev => [...prev, {
              id: `complete_${Date.now()}`,
              type: 'success',
              message: '✨ All processing completed successfully!',
              timestamp: new Date().toISOString()
            }]);
            
            return currentResults; // Return unchanged
          });
          
          // Stop streaming when complete
          setTimeout(() => stopEventStream(), 500); // Reduced delay
        }, 100); // Small delay to ensure all state updates are processed
        
      } catch (error) {
        console.error('Error parsing complete event:', error);
        // Fallback: still stop streaming
        setTimeout(() => stopEventStream(), 500);
      }
    });

    return newEventSource;
  };

  // Function to stop streaming
  const stopEventStream = () => {
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
    }
    setIsStreaming(false);
    setCurrentRequestId(null);
    // Keep agent states and grouped events for reference, but clear streaming state
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [eventSource]);

  // Auto-scroll to latest event when new events are added
  useEffect(() => {
    if (streamingEvents.length > 0) {
      const eventsContainer = document.querySelector('.events-container');
      if (eventsContainer) {
        eventsContainer.scrollTop = eventsContainer.scrollHeight;
      }
    }
  }, [streamingEvents]);

  // Helper function to render agent results in streaming view
  const renderAgentResult = (agentName, resultSnippet) => {
    // Normalize agent name for checks
    const lowerName = (agentName || '').toLowerCase();

    // Try parsing JSON first
    try {
      const parsed = JSON.parse(resultSnippet);

      // If this is the Summary Agent (or parsed contains summary fields for summary), render its specific fields
      if (parsed.market_verdict || parsed.financial_verdict || parsed.product_verdict || parsed.final_recommendation || lowerName.includes('summary')) {
        return (
          <div className="streaming-agent-result">
            {parsed.market_verdict && (
              <div className="result-field">
                <strong>🧠 Market Verdict:</strong>
                <p>{parsed.market_verdict}</p>
              </div>
            )}

            {parsed.financial_verdict && (
              <div className="result-field">
                <strong>💰 Financial Verdict:</strong>
                <p>{parsed.financial_verdict}</p>
              </div>
            )}

            {parsed.product_verdict && (
              <div className="result-field">
                <strong>📦 Product Verdict:</strong>
                <p>{parsed.product_verdict}</p>
              </div>
            )}

            {parsed.final_recommendation && (
              <div className="result-field">
                <strong>🎯 Final Recommendation:</strong>
                <div className="final-recommendation-badge">{String(parsed.final_recommendation)}</div>
                {parsed.rationale && <p className="rationale-text">{parsed.rationale}</p>}
              </div>
            )}

            {parsed.confidence_score !== undefined && parsed.confidence_score !== null && (
              <div className="result-field">
                <strong>📈 Confidence:</strong>
                <span className="confidence-score">{(typeof parsed.confidence_score === 'string' ? parseFloat(parsed.confidence_score) : parsed.confidence_score)}/10</span>
              </div>
            )}

            {/* Fallback: also show any summary/verdict/viability fields if present */}
            {parsed.summary && (
              <div className="result-field">
                <strong>📝 Analysis:</strong>
                <p>{parsed.summary}</p>
              </div>
            )}

            {parsed.verdict && (
              <div className="result-field">
                <strong>🎯 Verdict:</strong>
                <span className={`verdict-badge ${parsed.verdict.toLowerCase()}`}>
                  {parsed.verdict}
                </span>
              </div>
            )}

            {parsed.viability_score !== undefined && parsed.viability_score !== null && (
              <div className="result-field">
                <strong>📊 Viability Score:</strong>
                <div className="streaming-score-display">
                  <span className="streaming-score-value">{parsed.viability_score}/10</span>
                  <div className="streaming-score-bar">
                    <div 
                      className="streaming-score-fill" 
                      style={{ width: `${(parsed.viability_score / 10) * 100}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      }

      // Default rendering for other parsed agent outputs (market, product, finance etc)
      return (
        <div className="streaming-agent-result">
          {parsed.summary && (
            <div className="result-field">
              <strong>📝 Analysis:</strong>
              <p>{parsed.summary}</p>
            </div>
          )}

          {parsed.verdict && (
            <div className="result-field">
              <strong>🎯 Verdict:</strong>
              <span className={`verdict-badge ${parsed.verdict.toLowerCase()}`}>
                {parsed.verdict}
              </span>
            </div>
          )}

          {parsed.viability_score !== null && parsed.viability_score !== undefined && (
            <div className="result-field">
              <strong>📊 Viability Score:</strong>
              <div className="streaming-score-display">
                <span className="streaming-score-value">{parsed.viability_score}/10</span>
                <div className="streaming-score-bar">
                  <div 
                    className="streaming-score-fill" 
                    style={{ width: `${(parsed.viability_score / 10) * 100}%` }}
                  ></div>
                </div>
              </div>
            </div>
          )}

          {parsed.final_recommendation && (
            <div className="result-field">
              <strong>🎯 Final Recommendation:</strong>
              <div className="final-recommendation-badge">
                {parsed.final_recommendation}
              </div>
              {parsed.rationale && (
                <p className="rationale-text">{parsed.rationale}</p>
              )}
            </div>
          )}

          {parsed.confidence_score !== null && parsed.confidence_score !== undefined && (
            <div className="result-field">
              <strong>🎯 Confidence:</strong>
              <span className="confidence-score">{parsed.confidence_score}/10</span>
            </div>
          )}
        </div>
      );
    } catch (e) {
      // If not JSON or parsing failed, try regex-based extraction including summary-agent fields
      const extracted = {
        summary: null,
        verdict: null,
        viability_score: null,
        confidence_score: null,
        user_personas: null,
        must_have_features: null,
        MVP_scope: null,
        GTM_strategy: null,
        market_verdict: null,
        financial_verdict: null,
        product_verdict: null,
        final_recommendation: null,
        rationale: null
      };

      // Generic fields
      const summaryMatch = resultSnippet.match(/"summary":\s*"([\s\S]*?)"(?:,|\n|\})/);
      if (summaryMatch) extracted.summary = summaryMatch[1];

      const verdictMatch = resultSnippet.match(/"verdict":\s*"([^\"]+)"/);
      if (verdictMatch) extracted.verdict = verdictMatch[1];

      const scoreMatch = resultSnippet.match(/"viability_score":\s*"?(\d+(?:\.\d+)?)"?/);
      if (scoreMatch) extracted.viability_score = parseFloat(scoreMatch[1]);

      const confidenceMatch = resultSnippet.match(/"confidence_score":\s*"?(\d+(?:\.\d+)?)"?/);
      if (confidenceMatch) extracted.confidence_score = parseFloat(confidenceMatch[1]);

      // Product strategy fields
      const mvpMatch = resultSnippet.match(/"MVP_scope":\s*"([\s\S]*?)"(?:,|\n|\})/);
      if (mvpMatch) extracted.MVP_scope = mvpMatch[1];

      const gtmMatch = resultSnippet.match(/"GTM_strategy":\s*"([\s\S]*?)"(?:,|\n|\})/);
      if (gtmMatch) extracted.GTM_strategy = gtmMatch[1];

      // Summary-agent specific fields
      const marketVerdictMatch = resultSnippet.match(/"market_verdict":\s*"([\s\S]*?)"(?:,|\n|\})/);
      if (marketVerdictMatch) extracted.market_verdict = marketVerdictMatch[1];

      const financialVerdictMatch = resultSnippet.match(/"financial_verdict":\s*"([\s\S]*?)"(?:,|\n|\})/);
      if (financialVerdictMatch) extracted.financial_verdict = financialVerdictMatch[1];

      const productVerdictMatch = resultSnippet.match(/"product_verdict":\s*"([\s\S]*?)"(?:,|\n|\})/);
      if (productVerdictMatch) extracted.product_verdict = productVerdictMatch[1];

      const finalRecommendationMatch = resultSnippet.match(/"final_recommendation":\s*"([^"]+)"/);
      if (finalRecommendationMatch) extracted.final_recommendation = finalRecommendationMatch[1];

      const rationaleMatch = resultSnippet.match(/"rationale":\s*"([\s\S]*?)"(?:,|\n|\})/);
      if (rationaleMatch) extracted.rationale = rationaleMatch[1];

      // Render extracted structured data (prefer summary-agent views if present)
      return (
        <div className="streaming-agent-result">
          {extracted.market_verdict ? (
            <div>
              {extracted.market_verdict && (
                <div className="result-field">
                  <strong>🧠 Market Verdict:</strong>
                  <p>{extracted.market_verdict}</p>
                </div>
              )}

              {extracted.financial_verdict && (
                <div className="result-field">
                  <strong>💰 Financial Verdict:</strong>
                  <p>{extracted.financial_verdict}</p>
                </div>
              )}

              {extracted.product_verdict && (
                <div className="result-field">
                  <strong>📦 Product Verdict:</strong>
                  <p>{extracted.product_verdict}</p>
                </div>
              )}

              {extracted.final_recommendation && (
                <div className="result-field">
                  <strong>🎯 Final Recommendation:</strong>
                  <div className="final-recommendation-badge">{extracted.final_recommendation}</div>
                  {extracted.rationale && <p className="rationale-text">{extracted.rationale}</p>}
                </div>
              )}

              {extracted.confidence_score !== null && extracted.confidence_score !== undefined && (
                <div className="result-field">
                  <strong>📈 Confidence:</strong>
                  <span className="confidence-score">{extracted.confidence_score}/10</span>
                </div>
              )}
            </div>
          ) : (
            // Fallback for non-summary agents
            <div>
              {extracted.summary ? (
                <div className="result-field">
                  <strong>📝 Analysis:</strong>
                  <p>{extracted.summary}</p>
                </div>
              ) : (
                <div className="result-field">
                  <strong>📄 Response:</strong>
                  <p>{resultSnippet.substring(0, 300)}{resultSnippet.length > 300 ? '...' : ''}</p>
                </div>
              )}

              {extracted.verdict && (
                <div className="result-field">
                  <strong>🎯 Verdict:</strong>
                  <span className={`verdict-badge ${extracted.verdict.toLowerCase()}`}>
                    {extracted.verdict}
                  </span>
                </div>
              )}

              {extracted.viability_score !== null && (
                <div className="result-field">
                  <strong>📊 Viability Score:</strong>
                  <div className="score-display-inline">
                    <span className="score-value">{extracted.viability_score}/10</span>
                    <div className="score-bar-mini">
                      <div 
                        className="score-fill-mini" 
                        style={{ width: `${(extracted.viability_score / 10) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      );
    }
  };

  return (
    <div className="dashboard">
      <Navigation />

      <main className="dashboard-main">
        <div className="dashboard-content">
          {/* User Profile & Budget Section */}
          <section className="profile-section">
            {/* Quick Usage Summary */}
            {user.budget_info && (
              <div className="usage-summary-card">
                <h2>⚡ Quick Usage</h2>
                <div className="usage-stats">
                  <div className="usage-stat">
                    <span className="stat-label">Daily</span>
                    <span className="stat-value">
                      ${user.budget_info.usage.daily_spent.toFixed(4)} / ${user.budget_info.limits.daily_limit.toFixed(4)}
                    </span>
                  </div>
                  <div className="usage-stat">
                    <span className="stat-label">Monthly</span>
                    <span className="stat-value">
                      ${user.budget_info.usage.monthly_spent.toFixed(4)} / ${user.budget_info.limits.monthly_limit.toFixed(4)}
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div className="profile-card">
              <h2>📊 Account Overview</h2>
              <div className="profile-info">
                <div className="info-item">
                  <span className="label">Email:</span>
                  <span className="value">{user.email}</span>
                </div>
                <div className="info-item">
                  <span className="label">Plan:</span>
                  <span className="value" style={{ color: getTierColor(user.tier) }}>
                    {user.tier}
                  </span>
                </div>
              </div>

              {/* Prompt Sanitization Settings */}
              <div className="settings-section">
                <h3>🛡️ Security Settings</h3>
                <div className="setting-item">
                  <div className="setting-info">
                    <span className="setting-label">Prompt Sanitization</span>
                    <span className="setting-description">
                      Filter potentially harmful content from your prompts
                    </span>
                  </div>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={user.prompt_sanitization || false}
                      onChange={handlePromptSanitizationToggle}
                      disabled={updatingSettings}
                    />
                    <span className="toggle-slider"></span>
                  </label>
                </div>
              </div>

              {user.budget_info && (
                <div className="budget-info">
                  <h3>💰 Usage & Limits</h3>
                  
                  {/* Daily Usage */}
                  <div className="budget-item">
                    <div className="budget-label">
                      <span>Daily</span>
                      <span className="budget-amounts">
                        ${user.budget_info.usage.daily_spent.toFixed(2)} / ${user.budget_info.limits.daily_limit.toFixed(2)}
                      </span>
                    </div>
                    <div className="budget-bar">
                      <div 
                        className="budget-fill"
                        style={{ 
                          width: `${Math.min(getBudgetUsagePercentage(user.budget_info.usage.daily_spent, user.budget_info.limits.daily_limit), 100)}%`,
                          backgroundColor: getBudgetColor(getBudgetUsagePercentage(user.budget_info.usage.daily_spent, user.budget_info.limits.daily_limit))
                        }}
                      />
                    </div>
                    <div className="usage-percentage">
                      {getBudgetUsagePercentage(user.budget_info.usage.daily_spent, user.budget_info.limits.daily_limit).toFixed(1)}% used
                    </div>
                  </div>

                  {/* Monthly Usage */}
                  <div className="budget-item">
                    <div className="budget-label">
                      <span>Monthly</span>
                      <span className="budget-amounts">
                        ${user.budget_info.usage.monthly_spent.toFixed(2)} / ${user.budget_info.limits.monthly_limit.toFixed(2)}
                      </span>
                    </div>
                    <div className="budget-bar">
                      <div 
                        className="budget-fill"
                        style={{ 
                          width: `${Math.min(getBudgetUsagePercentage(user.budget_info.usage.monthly_spent, user.budget_info.limits.monthly_limit), 100)}%`,
                          backgroundColor: getBudgetColor(getBudgetUsagePercentage(user.budget_info.usage.monthly_spent, user.budget_info.limits.monthly_limit))
                        }}
                      />
                    </div>
                    <div className="usage-percentage">
                      {getBudgetUsagePercentage(user.budget_info.usage.monthly_spent, user.budget_info.limits.monthly_limit).toFixed(1)}% used
                    </div>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Analyzer Section */}
          <section className="analyzer-section">
            <div className="input-card">
              <h2>💡 Your Startup Idea</h2>
              <form onSubmit={handleSubmit}>
                {/* Prompt Selection Mode Toggle */}
                <div className="input-group">
                  <label>Prompt Selection Mode:</label>
                  <div className="prompt-mode-toggle">
                    <label className={`mode-option ${promptSelectionMode === 'global' ? 'active' : ''}`}>
                      <input
                        type="radio"
                        value="global"
                        checked={promptSelectionMode === 'global'}
                        onChange={(e) => handlePromptSelectionModeChange(e.target.value)}
                        disabled={loading}
                      />
                      <span>Global Prompt</span>
                    </label>
                    <label className={`mode-option ${promptSelectionMode === 'agent' ? 'active' : ''}`}>
                      <input
                        type="radio"
                        value="agent"
                        checked={promptSelectionMode === 'agent'}
                        onChange={(e) => handlePromptSelectionModeChange(e.target.value)}
                        disabled={loading}
                      />
                      <span>Per-Agent Prompts</span>
                    </label>
                  </div>
                </div>

                {/* Global Prompt Selection */}
                {promptSelectionMode === 'global' && (
                  <div className="input-group">
                    <label htmlFor="prompt-select">Select Analysis Prompt:</label>
                    <select
                      id="prompt-select"
                      value={selectedPromptId}
                      onChange={(e) => setSelectedPromptId(e.target.value)}
                      disabled={loading || promptsLoading}
                      className="prompt-select"
                    >
                      <option value="">Default Analysis</option>
                      {prompts.map(prompt => (
                          <option key={prompt.prompt_id} value={prompt.prompt_id}>
                            {prompt.name} (v{prompt.version})
                          </option>
                        ))
                      }
                    </select>
                    {promptsLoading && (
                      <div className="prompt-loading">Loading prompts...</div>
                    )}
                  </div>
                )}

                {/* Per-Agent Prompt Selection */}
                {promptSelectionMode === 'agent' && (
                  <div className="input-group">
                    <label>Select Agent Versions:</label>
                    <div className="agent-prompts-container">
                      {Object.entries(agentVersions).map(([agentKey, versions]) => (
                        <div key={agentKey} className="agent-prompt-group">
                          <h4>{getAgentDisplayName(agentKey)}</h4>
                          <div className="version-options">
                            <label className="version-option">
                              <input
                                type="radio"
                                name={agentKey}
                                value=""
                                checked={agentPrompts[agentKey] === ''}
                                onChange={(e) => handleAgentPromptChange(agentKey, '')}
                                disabled={loading}
                              />
                              <span>Skip</span>
                            </label>
                            {versions.map(version => (
                              <label key={version.id} className="version-option">
                                <input
                                  type="radio"
                                  name={agentKey}
                                  value={version.id}
                                  checked={agentPrompts[agentKey] === version.id}
                                  onChange={(e) => handleAgentPromptChange(agentKey, version.id)}
                                  disabled={loading}
                                />
                                <span>{version.name} (v{version.version})</span>
                              </label>
                            ))}
                          </div>
                          {versions.length === 0 && (
                            <div className="no-prompts-message">
                              No prompts available for this agent
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                    <div className="agent-selection-note">
                      <p>💡 Select one version per agent or skip agents you don't want to use. At least one agent must be selected.</p>
                    </div>
                  </div>
                )}

                <div className="input-group">
                  <label htmlFor="idea">Describe your startup idea:</label>
                  <textarea
                    id="idea"
                    value={idea}
                    onChange={(e) => setIdea(e.target.value)}
                    placeholder="Enter your startup idea here... Be as detailed as possible about the problem you're solving, your target market, and your proposed solution."
                    disabled={loading}
                  />
                </div>
                <button 
                  type="submit" 
                  className="submit-btn" 
                  disabled={loading || !idea.trim() || !isAgentPromptSelectionValid()}
                >
                  {loading ? (isStreaming ? 'Processing...' : 'Analyzing...') : 'Analyze Idea'}
                </button>
              </form>

              {/* Streaming Events Display */}
              {isStreaming && (
                <div className="streaming-events">
                  <h3>🔄 Live Analysis Progress</h3>
                  <div className="events-container">
                    {streamingEvents.map((event, index) => (
                      <div key={index} className={`event-item ${event.type || 'info'}`}>
                        <span className="event-timestamp">
                          {new Date(event.timestamp).toLocaleTimeString([], { 
                            hour12: false, 
                            hour: '2-digit', 
                            minute: '2-digit', 
                            second: '2-digit' 
                          })}
                        </span>
                        <span className="event-message">
                          {event.message}
                          {event.agent && <span className="event-agent">{event.agent}</span>}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="results-card">
              <h2>📊 Analysis Results</h2>
              <div className="results-content">
                {error && (
                  <div className={`error ${error.type === 'prompt_injection' ? 'error-security' : ''}`}>
                    {error.type === 'prompt_injection' && (
                      <div className="error-icon">🛡️</div>
                    )}
                    <div className="error-content">
                      <strong>{error.type === 'prompt_injection' ? 'Security Alert' : 'Error'}:</strong>
                      <span className="error-message">
                        {typeof error === 'string' ? error : error.message || 'An error occurred'}
                      </span>
                      {error.type === 'prompt_injection' && (
                        <div className="error-suggestion">
                          💡 Tip: Try rephrasing your idea in simpler, business-focused terms.
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Show streaming agent status */}
                {isStreaming && (Object.keys(agentResults).length > 0 || Object.keys(agentStates).length > 0) && (
                  <div className="streaming-agents-container">
                    {/* Show thinking agents */}
                    {Object.entries(agentStates).map(([agentName, state]) => {
                      if (state === 'thinking' && !agentResults[agentName]) {
                        return (
                          <div key={agentName} className="streaming-agent-card thinking">
                            <div className="streaming-agent-header">
                              <span className="streaming-agent-icon">
                                {agentName === 'Market Research Agent' && '🧠'}
                                {agentName === 'Financial Advisor' && '💰'}
                                {agentName === 'Product Strategy Agent' && '📦'}
                                {agentName === 'Summary Agent' && '📋'}
                              </span>
                              <span className="streaming-agent-name">{agentName}</span>
                              <span className="streaming-agent-status thinking">🤔 Thinking...</span>
                            </div>
                            <div className="streaming-agent-preview">
                              Analyzing your startup idea...
                            </div>
                          </div>
                        );
                      }
                      return null;
                    })}
                    
                    {/* Show completed agents */}
                    {Object.entries(agentResults).map(([agentName, resultSnippet]) => (
                      <div key={agentName} className="streaming-agent-card completed">
                        <div className="streaming-agent-header">
                          <span className="streaming-agent-icon">
                            {agentName === 'Market Research Agent' && '🧠'}
                            {agentName === 'Financial Advisor' && '💰'}
                            {agentName === 'Product Strategy Agent' && '📦'}
                            {agentName === 'Summary Agent' && '📋'}
                          </span>
                          <span className="streaming-agent-name">{agentName}</span>
                          <span className="streaming-agent-status completed">✅ Done</span>
                        </div>
                        <div className="streaming-agent-preview">
                          {getStreamingPreview(agentName, resultSnippet)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {result && analysisComplete && (
                  <div>
                    {/* Individual Agent Analysis Cards */}
                    {result.agents && Object.keys(result.agents).length > 0 && (
                      <div className="agent-analysis-container">
                        {Object.entries(result.agents).map(([agentName, agentData]) => (
                          <div key={agentName} className="agent-analysis-card">
                            <h3>
                              {agentName === 'Market Research Agent' && '🧠'}
                              {agentName === 'Financial Advisor' && '💰'}
                              {agentName === 'Product Strategy Agent' && '📦'}
                              {agentName === 'Summary Agent' && '📋'}
                              {' '}
                              {agentName}
                            </h3>
                            <div className="agent-content">
                              {agentData.isSummaryAgent ? (
                                <>
                                  {agentData.market_verdict && (
                                    <div className="agent-field">
                                      <strong>🧠 Market Verdict:</strong>
                                      <p>{agentData.market_verdict}</p>
                                    </div>
                                  )}

                                  {agentData.financial_verdict && (
                                    <div className="agent-field">
                                      <strong>💰 Financial Verdict:</strong>
                                      <p>{agentData.financial_verdict}</p>
                                    </div>
                                  )}

                                  {agentData.product_verdict && (
                                    <div className="agent-field">
                                      <strong>📦 Product Verdict:</strong>
                                      <p>{agentData.product_verdict}</p>
                                    </div>
                                  )}

                                  {agentData.final_recommendation && (
                                    <div className="agent-field">
                                      <strong>🎯 Final Recommendation:</strong>{' '}
                                      <span className={`recommendation-badge ${String(agentData.final_recommendation).toLowerCase()}`}>
                                        {String(agentData.final_recommendation).toUpperCase()}
                                      </span>
                                    </div>
                                  )}

                                  {agentData.rationale && (
                                    <div className="agent-field">
                                      <strong>📝 Rationale:</strong> {agentData.rationale}
                                    </div>
                                  )}

                                  {agentData.confidence_score !== undefined && agentData.confidence_score !== null && (
                                    <div className="agent-field">
                                      <strong>📈 Confidence:</strong>{' '}
                                      {(typeof agentData.confidence_score === 'string' ? parseFloat(agentData.confidence_score) : agentData.confidence_score).toFixed(1)}/10
                                    </div>
                                  )}

                                  {/* Still show summary if present */}
                                  {agentData.summary && (
                                    <div className="agent-field">
                                      <strong>📝 Summary:</strong> {agentData.summary}
                                    </div>
                                  )}
                                </>
                              ) : (
                                // Non-summary agent rendering (keeps existing behavior)
                                <>
                                  {agentData.summary && (
                                    <div className="agent-field">
                                      <strong>📝 Summary:</strong> {agentData.summary}
                                    </div>
                                  )}

                                  {agentData.verdict && (
                                    <div className="agent-field">
                                      <strong>🎯 Verdict:</strong>{' '}
                                      <span className={`verdict-badge ${agentData.verdict.toLowerCase()}`}>
                                        {agentData.verdict}
                                      </span>
                                    </div>
                                  )}

                                  {agentData.viability_score !== null && agentData.viability_score !== undefined && (
                                    <div className="agent-field">
                                      <strong>📊 Viability Score:</strong>{' '}
                                      <span className="score-display">
                                        {agentData.viability_score}/10
                                        <div className="score-bar-inline">
                                          <div 
                                            className="score-fill-inline" 
                                            style={{ width: `${(agentData.viability_score / 10) * 100}%` }}
                                          ></div>
                                        </div>
                                      </span>
                                    </div>
                                  )}

                                  {!agentData.summary && !agentData.verdict && agentData.viability_score === null && (
                                    <div className="agent-field">
                                      <strong>📄 Response:</strong> {agentData.raw || 'No data available'}
                                    </div>
                                  )}
                                </>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {/* Final Recommendation (if available from Summary Agent) */}
                    {result.final_recommendation && (
                      <div className="analysis-section">
                        <h3>🎯 Final Recommendation</h3>
                        
                        <div className={getRecommendationStyle(result.final_recommendation)}>
                          {result.final_recommendation.toUpperCase()}
                        </div>
                        
                        {result.rationale && (
                          <p style={{ marginTop: '15px' }}>{result.rationale}</p>
                        )}
                        
                        {result.confidence_score !== undefined && (
                          <div className="confidence-section" style={{ marginTop: '15px' }}>
                            <h4 style={{ color: '#a855f7', fontSize: '1rem', marginBottom: '5px' }}>
                              Confidence Score
                            </h4>
                            <div style={{ 
                              fontSize: '2rem', 
                              fontWeight: 'bold', 
                              color: getConfidenceColor(result.confidence_score) 
                            }}>
                              {(typeof result.confidence_score === 'number' ? result.confidence_score : parseFloat(result.confidence_score) || 0).toFixed(1)}/10
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Legacy fallback display */}
                    {(!result.agents || Object.keys(result.agents).length === 0) && (
                      <div>
                        {/* Market Verdict */}
                        {result.market_verdict && (
                          <div className="analysis-section">
                            <h3>🧠 Market Analysis</h3>
                            <p>{result.market_verdict}</p>
                          </div>
                        )}
                        
                        {/* Financial Verdict */}
                        {result.financial_verdict && (
                          <div className="analysis-section">
                            <h3>💰 Financial Analysis</h3>
                            <p>{result.financial_verdict}</p>
                          </div>
                        )}
                        
                        {/* Product Verdict */}
                        {result.product_verdict && (
                          <div className="analysis-section">
                            <h3>📦 Product Strategy</h3>
                            <p>{result.product_verdict}</p>
                          </div>
                        )}
                        
                        {/* Fallback for summary if structured data is not available */}
                        {result.summary && !result.market_verdict && (
                          <div className="analysis-section">
                            <h3>📝 Analysis Summary</h3>
                            <p>{result.summary}</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Show streaming progress when not complete */}
                {(loading || isStreaming) && !analysisComplete && (
                  <div className="loading">
                    <div className="loading-spinner"></div>
                    <p>Our AI agents are analyzing your startup idea...</p>
                    <p>This may take a few moments.</p>
                    {Object.keys(agentResults).length > 0 && (
                      <div className="partial-results">
                        <p>📋 Results received from {Object.keys(agentResults).length} agent(s)...</p>
                      </div>
                    )}
                  </div>
                )}

                {!loading && !isStreaming && !result && !error && (
                  <div className="empty-state">
                    Enter your startup idea and click "Analyze Idea" to get started.
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;

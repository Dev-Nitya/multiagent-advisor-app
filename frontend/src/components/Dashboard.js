import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import Navigation from './Navigation';
import axios from 'axios';
import authService from '../services/authService';
import promptService from '../services/promptService';
import './Dashboard.css';

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

    try {
      const requestData = {
        idea: idea.trim(),
        user_id: user.user_id,
        request_id: `req-${Date.now()}`
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

      const response = await axios.post('/evaluate', requestData);
      setResult(response.data);
      // Refresh user profile to update budget usage
      await refreshUser();
    } catch (err) {
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
        return 'verdict viable';
      case 'no-go':
        return 'verdict not-viable';
      case 'pivot':
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
                <div className="info-item">
                  <span className="label">Member Since:</span>
                  <span className="value">
                    {new Date(user.created_at).toLocaleDateString()}
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
                  {loading ? 'Analyzing...' : 'Analyze Idea'}
                </button>
              </form>
            </div>

            <div className="results-card">
              <h2>📊 Analysis Results</h2>
              <div className="results-content">
                {loading && (
                  <div className="loading">
                    <div className="loading-spinner"></div>
                    <p>Our AI agents are analyzing your startup idea...</p>
                    <p>This may take a few moments.</p>
                  </div>
                )}

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

                {result && !loading && (
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
                    
                    {/* Final Recommendation */}
                    <div className="analysis-section">
                      <h3>🎯 Final Recommendation</h3>
                      
                      {result.final_recommendation && (
                        <div className={getRecommendationStyle(result.final_recommendation)}>
                          {result.final_recommendation.toUpperCase()}
                        </div>
                      )}
                      
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
                            {(result.confidence_score).toFixed(1)}/10
                          </div>
                        </div>
                      )}
                    </div>
                    
                    {/* Fallback for summary if structured data is not available */}
                    {result.summary && !result.market_verdict && (
                      <div className="analysis-section">
                        <h3>📝 Analysis Summary</h3>
                        <p>{result.summary}</p>
                      </div>
                    )}
                  </div>
                )}

                {!loading && !result && !error && (
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

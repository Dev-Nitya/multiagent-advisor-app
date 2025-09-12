import React, { useState } from 'react';
import axios from 'axios';
import './index.css';

function App() {
  const [idea, setIdea] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!idea.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await axios.post('/evaluate', {
        idea: idea.trim()
      });
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred while evaluating your startup idea.');
    } finally {
      setLoading(false);
    }
  };

  const getRecommendationStyle = (recommendation) => {
    switch (recommendation?.toLowerCase()) {
      case 'launch':
        return 'verdict viable';
      case 'abandon':
        return 'verdict not-viable';
      case 'iterate':
        return 'verdict uncertain';
      default:
        return 'verdict uncertain';
    }
  };

  const getConfidenceColor = (score) => {
    if (score >= 8) return '#4ade80'; // Green
    if (score >= 6) return '#fbbf24'; // Yellow
    if (score >= 4) return '#fb923c'; // Orange
    return '#f87171'; // Red
  };

  return (
    <div className="app">
      <header className="header">
        <h1>🚀 Multi-Agent Startup Advisor</h1>
        <p>AI-powered analysis of your startup ideas using multiple specialized agents</p>
      </header>

      <main className="main-content">
        <section className="input-section">
          <div className="input-card">
            <h2>💡 Your Startup Idea</h2>
            <form onSubmit={handleSubmit}>
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
                disabled={loading || !idea.trim()}
              >
                {loading ? 'Analyzing...' : 'Analyze Idea'}
              </button>
            </form>
          </div>
        </section>

        <section className="results-section">
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
                <div className="error">
                  <strong>Error:</strong> {error}
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
                    <h3>� Final Recommendation</h3>
                    
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
                          {result.confidence_score}/10
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
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center', 
                  height: '200px',
                  color: '#9ca3af',
                  fontSize: '1.1rem'
                }}>
                  Enter your startup idea and click "Analyze Idea" to get started.
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;

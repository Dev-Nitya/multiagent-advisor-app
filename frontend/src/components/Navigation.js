import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './Navigation.css';

const Navigation = () => {
  const { user, logout } = useAuth();
  const location = useLocation();

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

  return (
    <header className="nav-header">
      <div className="nav-content">
        <div className="nav-title">
          <h1>🚀 Multi-Agent Startup Advisor</h1>
          <p>AI-powered analysis of your startup ideas using multiple specialized agents</p>
        </div>
        
        <div className="nav-controls">
          <nav className="nav-links">
            <Link 
              to="/dashboard" 
              className={`nav-link ${location.pathname === '/dashboard' ? 'active' : ''}`}
            >
              📊 Dashboard
            </Link>
            <Link 
              to="/prompts" 
              className={`nav-link ${location.pathname === '/prompts' ? 'active' : ''}`}
            >
              📝 Prompts
            </Link>
            <Link 
              to="/cost-dashboard" 
              className={`nav-link ${location.pathname === '/cost-dashboard' ? 'active' : ''}`}
            >
              💰 Cost Dashboard
            </Link>
            {user.tier === 'ENTERPRISE' && (
              <Link 
                to="/admin" 
                className={`nav-link ${location.pathname === '/admin' ? 'active' : ''}`}
              >
                ⚙️ Admin Panel
              </Link>
            )}
          </nav>
          
          <div className="user-section">
            <div className="user-info">
              <span className="user-name">👋 {user.full_name}</span>
              <span className="user-tier" style={{ color: getTierColor(user.tier) }}>
                {user.tier} Plan
              </span>
            </div>
            <button onClick={logout} className="logout-btn">
              Logout
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navigation;

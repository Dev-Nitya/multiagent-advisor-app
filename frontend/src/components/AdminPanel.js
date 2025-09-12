import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import Navigation from './Navigation';
import axios from 'axios';
import './AdminPanel.css';

const AdminPanel = () => {
  const { user, logout } = useAuth();
  const [globalSettings, setGlobalSettings] = useState({
    prompt_sanitization_enabled: true
  });
  const [userSettings, setUserSettings] = useState({
    user_id: '',
    prompt_sanitization: null
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    fetchGlobalSettings();
  }, []);

  const fetchGlobalSettings = async () => {
    try {
      const response = await axios.get('/admin/prompt_sanitization');
      setGlobalSettings(response.data);
    } catch (error) {
      showMessage('error', handleError(error, 'Failed to fetch global settings'));
    }
  };

  const fetchUserSettings = async () => {
    if (!userSettings.user_id.trim()) {
      showMessage('error', 'Please enter a user ID');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.get(`/admin/users/${userSettings.user_id}/prompt_sanitization`);
      setUserSettings(prev => ({
        ...prev,
        prompt_sanitization: response.data.prompt_sanitization
      }));
      showMessage('success', 'User settings fetched successfully');
    } catch (error) {
      showMessage('error', handleError(error, 'Failed to fetch user settings'));
    } finally {
      setLoading(false);
    }
  };

  const updateGlobalSettings = async () => {
    setLoading(true);
    try {
      await axios.post('/admin/prompt_sanitization', {
        enabled: globalSettings.prompt_sanitization_enabled
      });
      showMessage('success', 'Global settings updated successfully');
    } catch (error) {
      showMessage('error', handleError(error, 'Failed to update global settings'));
    } finally {
      setLoading(false);
    }
  };

  const updateUserSettings = async () => {
    if (!userSettings.user_id.trim()) {
      showMessage('error', 'Please enter a user ID');
      return;
    }

    if (userSettings.prompt_sanitization === null) {
      showMessage('error', 'Please select a prompt sanitization setting');
      return;
    }

    setLoading(true);
    try {
      await axios.post(`/admin/users/${userSettings.user_id}/prompt_sanitization`, {
        enabled: userSettings.prompt_sanitization
      });
      showMessage('success', 'User settings updated successfully');
    } catch (error) {
      showMessage('error', handleError(error, 'Failed to update user settings'));
    } finally {
      setLoading(false);
    }
  };

  const showMessage = (type, text) => {
    // Ensure text is always a string
    const messageText = typeof text === 'string' ? text : 'An error occurred';
    setMessage({ type, text: messageText });
    setTimeout(() => setMessage({ type: '', text: '' }), 5000);
  };

  const handleError = (error, fallbackMessage) => {
    let errorMessage = fallbackMessage;
    
    if (error.response?.data) {
      if (typeof error.response.data.detail === 'string') {
        errorMessage = error.response.data.detail;
      } else if (Array.isArray(error.response.data.detail)) {
        errorMessage = error.response.data.detail.map(err => 
          `${err.loc?.join(' ')}: ${err.msg}`
        ).join(', ');
      } else if (error.response.data.message) {
        errorMessage = error.response.data.message;
      }
    }
    
    return errorMessage;
  };

  // Basic access control - in a real app, you'd check for admin role
  if (user.tier !== 'ENTERPRISE') {
    return (
      <div className="admin-container">
        <div className="access-denied">
          <h2>🚫 Access Denied</h2>
          <p>Admin panel is only available for Enterprise tier users.</p>
          <button onClick={() => window.history.back()} className="back-btn">
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-container">
      <Navigation />

      <main className="admin-main">
        {message.text && (
          <div className={`message ${message.type}`}>
            {typeof message.text === 'string' ? message.text : 'A message occurred'}
          </div>
        )}

        <div className="admin-content">
          {/* Global Settings */}
          <section className="settings-section">
            <div className="settings-card">
              <h2>🌐 Global Settings</h2>
              <div className="setting-item">
                <div className="setting-info">
                  <h3>Prompt Sanitization</h3>
                  <p>Enable or disable prompt sanitization globally for all users</p>
                </div>
                <div className="setting-control">
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={globalSettings.prompt_sanitization_enabled}
                      onChange={(e) => setGlobalSettings(prev => ({
                        ...prev,
                        prompt_sanitization_enabled: e.target.checked
                      }))}
                      disabled={loading}
                    />
                    <span className="slider"></span>
                  </label>
                  <button 
                    onClick={updateGlobalSettings}
                    className="update-btn"
                    disabled={loading}
                  >
                    {loading ? 'Updating...' : 'Update'}
                  </button>
                </div>
              </div>
            </div>
          </section>

          {/* User-Specific Settings */}
          <section className="settings-section">
            <div className="settings-card">
              <h2>👤 User-Specific Settings</h2>
              <div className="user-search">
                <div className="search-input">
                  <label htmlFor="userId">User ID:</label>
                  <input
                    type="text"
                    id="userId"
                    value={userSettings.user_id}
                    onChange={(e) => setUserSettings(prev => ({
                      ...prev,
                      user_id: e.target.value,
                      prompt_sanitization: null
                    }))}
                    placeholder="Enter user ID"
                    disabled={loading}
                  />
                  <button 
                    onClick={fetchUserSettings}
                    className="fetch-btn"
                    disabled={loading || !userSettings.user_id.trim()}
                  >
                    Fetch Settings
                  </button>
                </div>
              </div>

              {userSettings.user_id && (
                <div className="setting-item">
                  <div className="setting-info">
                    <h3>Prompt Sanitization for User</h3>
                    <p>Override global setting for this specific user</p>
                    <small>Current setting: {
                      userSettings.prompt_sanitization === null 
                        ? 'Using global default' 
                        : userSettings.prompt_sanitization 
                          ? 'Enabled' 
                          : 'Disabled'
                    }</small>
                  </div>
                  <div className="setting-control">
                    <select
                      value={userSettings.prompt_sanitization === null ? 'default' : userSettings.prompt_sanitization.toString()}
                      onChange={(e) => {
                        const value = e.target.value === 'default' ? null : e.target.value === 'true';
                        setUserSettings(prev => ({
                          ...prev,
                          prompt_sanitization: value
                        }));
                      }}
                      disabled={loading}
                    >
                      <option value="default">Use Global Default</option>
                      <option value="true">Enabled</option>
                      <option value="false">Disabled</option>
                    </select>
                    <button 
                      onClick={updateUserSettings}
                      className="update-btn"
                      disabled={loading}
                    >
                      {loading ? 'Updating...' : 'Update'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* System Info */}
          <section className="settings-section">
            <div className="settings-card">
              <h2>📊 System Information</h2>
              <div className="system-info">
                <div className="info-item">
                  <span className="label">Current User:</span>
                  <span className="value">{user.email}</span>
                </div>
                <div className="info-item">
                  <span className="label">User Tier:</span>
                  <span className="value">{user.tier}</span>
                </div>
                <div className="info-item">
                  <span className="label">Global Sanitization:</span>
                  <span className="value">
                    {globalSettings.prompt_sanitization_enabled ? '✅ Enabled' : '❌ Disabled'}
                  </span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
};

export default AdminPanel;

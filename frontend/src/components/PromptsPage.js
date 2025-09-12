import React, { useState, useEffect, useMemo } from 'react';
import Navigation from './Navigation';
import promptService from '../services/promptService';
import './PromptsPage.css';

const PromptsPage = () => {
  const [prompts, setPrompts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [viewMode, setViewMode] = useState('detailed'); // 'detailed' or 'compact'
  
  const itemsPerPage = viewMode === 'compact' ? 24 : 12; // More items in compact view

  useEffect(() => {
    fetchPrompts();
  }, []);

  const fetchPrompts = async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await promptService.getAllPrompts();
      if (result.success) {
        setPrompts(result.data);
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError('An error occurred while fetching prompts');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  // Memoized filtering and sorting
  const filteredAndSortedPrompts = useMemo(() => {
    let filtered = prompts;

    // Filter by search term
    if (searchTerm) {
      filtered = filtered.filter(prompt => 
        prompt.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        prompt.author.toLowerCase().includes(searchTerm.toLowerCase()) ||
        prompt.changelog?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Filter by type
    if (filterType !== 'all') {
      filtered = filtered.filter(prompt => prompt.name.includes(filterType));
    }

    // Sort prompts
    filtered.sort((a, b) => {
      let aValue = a[sortBy];
      let bValue = b[sortBy];

      if (sortBy === 'created_at') {
        aValue = new Date(aValue);
        bValue = new Date(bValue);
      }

      if (sortOrder === 'asc') {
        return aValue > bValue ? 1 : -1;
      } else {
        return aValue < bValue ? 1 : -1;
      }
    });

    return filtered;
  }, [prompts, searchTerm, filterType, sortBy, sortOrder]);

  // Pagination
  const totalPages = Math.ceil(filteredAndSortedPrompts.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentPrompts = filteredAndSortedPrompts.slice(startIndex, endIndex);

  const handlePageChange = (page) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSearch = (e) => {
    setSearchTerm(e.target.value);
    setCurrentPage(1); // Reset to first page when searching
  };

  const handleFilterChange = (e) => {
    setFilterType(e.target.value);
    setCurrentPage(1);
  };

  const handleSortChange = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
    setCurrentPage(1);
  };

  const getUniquePromptTypes = () => {
    const types = new Set();
    prompts.forEach(prompt => {
      const type = prompt.name.split('_')[0];
      types.add(type);
    });
    return Array.from(types);
  };

  // Compact prompt card component for better performance
  const CompactPromptCard = ({ prompt }) => (
    <div className="prompt-card compact">
      <div className="compact-header">
        <h3>{prompt.name}</h3>
        <span className="compact-version">v{prompt.version}</span>
      </div>
      
      <div className="compact-meta">
        <span className="compact-author">👤 {prompt.author}</span>
        <span className="compact-date">📅 {formatDate(prompt.created_at)}</span>
      </div>

      {prompt.model_settings && (
        <div className="compact-model">
          <span className="model-info">
            🤖 {prompt.model_settings.provider} - {prompt.model_settings.model_name}
          </span>
        </div>
      )}

      {prompt.changelog && (
        <div className="compact-changelog">
          <p>{prompt.changelog}</p>
        </div>
      )}
    </div>
  );

  // Detailed prompt card component (existing design)
  const DetailedPromptCard = ({ prompt }) => (
    <div className="prompt-card detailed">
      <div className="prompt-header">
        <div className="prompt-title">
          <h3>{prompt.name}</h3>
          <span className="status-badge active">✅ Active</span>
        </div>
        <div className="prompt-version">
          v{prompt.version}
        </div>
      </div>

      <div className="prompt-meta">
        <div className="meta-item">
          <span className="meta-icon">👤</span>
          <span className="meta-label">Author:</span>
          <span className="meta-value">{prompt.author}</span>
        </div>
        
        <div className="meta-item">
          <span className="meta-icon">📅</span>
          <span className="meta-label">Created:</span>
          <span className="meta-value">{formatDate(prompt.created_at)}</span>
        </div>

        <div className="meta-item">
          <span className="meta-icon">🆔</span>
          <span className="meta-label">ID:</span>
          <span className="meta-value prompt-id">{prompt.prompt_id}</span>
        </div>
      </div>

      {prompt.changelog && (
        <div className="changelog-section">
          <div className="section-header">
            <span className="section-icon">📋</span>
            <h4>Changelog</h4>
          </div>
          <p className="changelog-text">{prompt.changelog}</p>
        </div>
      )}

      {prompt.model_settings && (
        <div className="model-settings">
          <div className="section-header">
            <span className="section-icon">🤖</span>
            <h4>AI Model Configuration</h4>
          </div>
          <div className="settings-container">
            <div className="setting-row">
              <div className="setting-item">
                <span className="setting-label">Provider</span>
                <span className="setting-value provider-badge">{prompt.model_settings.provider}</span>
              </div>
              <div className="setting-item">
                <span className="setting-label">Model</span>
                <span className="setting-value model-badge">{prompt.model_settings.model_name}</span>
              </div>
            </div>
            <div className="setting-row">
              <div className="setting-item">
                <span className="setting-label">Temperature</span>
                <span className="setting-value temp-badge">{prompt.model_settings.temperature}</span>
              </div>
              <div className="setting-item">
                <span className="setting-label">Max Tokens</span>
                <span className="setting-value tokens-badge">{prompt.model_settings.max_tokens}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="prompt-content">
        <div className="section-header">
          <span className="section-icon">📝</span>
          <h4>System Prompt</h4>
        </div>
        <div className="prompt-text">
          {prompt.prompt_text}
        </div>
      </div>

      {prompt.output_schema && (
        <div className="output-schema">
          <div className="section-header">
            <span className="section-icon">📊</span>
            <h4>Expected Output Format</h4>
          </div>
          <div className="schema-container">
            {Object.entries(prompt.output_schema).map(([key, value]) => (
              <div key={key} className="schema-field">
                <span className="field-name">{key}</span>
                <span className="field-description">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="prompts-page">
      <Navigation />

      <main className="prompts-main">
        <div className="prompts-content">
          <div className="page-header">
            <h1>📝 Prompt Management</h1>
            <p>View and manage all system prompts used by the AI agents</p>
            {!loading && !error && (
              <div className="stats-bar">
                <span className="total-count">
                  {filteredAndSortedPrompts.length} of {prompts.length} prompts
                </span>
              </div>
            )}
          </div>

          {/* Search and Filter Controls */}
          {!loading && !error && prompts.length > 0 && (
            <div className="controls-section">
              <div className="search-bar">
                <span className="search-icon">🔍</span>
                <input
                  type="text"
                  placeholder="Search prompts by name, author, or changelog..."
                  value={searchTerm}
                  onChange={handleSearch}
                  className="search-input"
                />
              </div>
              
              <div className="filter-controls">
                <div className="filter-group">
                  <label htmlFor="filter-type">Filter by Type:</label>
                  <select
                    id="filter-type"
                    value={filterType}
                    onChange={handleFilterChange}
                    className="filter-select"
                  >
                    <option value="all">All Types</option>
                    {getUniquePromptTypes().map(type => (
                      <option key={type} value={type}>
                        {type.charAt(0).toUpperCase() + type.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="sort-controls">
                  <span className="sort-label">Sort by:</span>
                  <button
                    className={`sort-btn ${sortBy === 'name' ? 'active' : ''}`}
                    onClick={() => handleSortChange('name')}
                  >
                    Name {sortBy === 'name' && (sortOrder === 'asc' ? '↑' : '↓')}
                  </button>
                  <button
                    className={`sort-btn ${sortBy === 'created_at' ? 'active' : ''}`}
                    onClick={() => handleSortChange('created_at')}
                  >
                    Date {sortBy === 'created_at' && (sortOrder === 'asc' ? '↑' : '↓')}
                  </button>
                  <button
                    className={`sort-btn ${sortBy === 'version' ? 'active' : ''}`}
                    onClick={() => handleSortChange('version')}
                  >
                    Version {sortBy === 'version' && (sortOrder === 'asc' ? '↑' : '↓')}
                  </button>
                  
                  <div className="view-toggle">
                    <button
                      className={`view-btn ${viewMode === 'detailed' ? 'active' : ''}`}
                      onClick={() => setViewMode('detailed')}
                      title="Detailed View"
                    >
                      📋
                    </button>
                    <button
                      className={`view-btn ${viewMode === 'compact' ? 'active' : ''}`}
                      onClick={() => setViewMode('compact')}
                      title="Compact View"
                    >
                      📑
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {loading && (
            <div className="loading-container">
              <div className="loading-spinner"></div>
              <p>Loading prompts...</p>
            </div>
          )}

          {error && (
            <div className="error-container">
              <div className="error">
                <strong>Error:</strong> {error}
              </div>
              <button onClick={fetchPrompts} className="retry-btn">
                🔄 Retry
              </button>
            </div>
          )}

          {!loading && !error && (
            <div className="prompts-container">
              {filteredAndSortedPrompts.length === 0 ? (
                <div className="no-prompts">
                  <h3>No prompts found</h3>
                  <p>
                    {searchTerm || filterType !== 'all' 
                      ? 'No prompts match your current filters. Try adjusting your search or filter criteria.'
                      : 'There are currently no prompts in the system.'
                    }
                  </p>
                  {(searchTerm || filterType !== 'all') && (
                    <button 
                      onClick={() => {
                        setSearchTerm('');
                        setFilterType('all');
                        setCurrentPage(1);
                      }}
                      className="clear-filters-btn"
                    >
                      Clear Filters
                    </button>
                  )}
                </div>
              ) : (
                <>
                  <div className={`prompts-grid ${viewMode}`}>
                    {currentPrompts.map((prompt) => 
                      viewMode === 'compact' ? (
                        <CompactPromptCard key={prompt.prompt_id} prompt={prompt} />
                      ) : (
                        <DetailedPromptCard key={prompt.prompt_id} prompt={prompt} />
                      )
                    )}
                  </div>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="pagination-container">
                      <div className="pagination">
                        <button
                          className="page-btn"
                          onClick={() => handlePageChange(currentPage - 1)}
                          disabled={currentPage === 1}
                        >
                          ← Previous
                        </button>

                        <div className="page-numbers">
                          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                            let pageNumber;
                            if (totalPages <= 5) {
                              pageNumber = i + 1;
                            } else if (currentPage <= 3) {
                              pageNumber = i + 1;
                            } else if (currentPage >= totalPages - 2) {
                              pageNumber = totalPages - 4 + i;
                            } else {
                              pageNumber = currentPage - 2 + i;
                            }

                            return (
                              <button
                                key={pageNumber}
                                className={`page-number ${currentPage === pageNumber ? 'active' : ''}`}
                                onClick={() => handlePageChange(pageNumber)}
                              >
                                {pageNumber}
                              </button>
                            );
                          })}
                        </div>

                        <button
                          className="page-btn"
                          onClick={() => handlePageChange(currentPage + 1)}
                          disabled={currentPage === totalPages}
                        >
                          Next →
                        </button>
                      </div>
                      
                      <div className="pagination-info">
                        Showing {startIndex + 1}-{Math.min(endIndex, filteredAndSortedPrompts.length)} of {filteredAndSortedPrompts.length} prompts
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default PromptsPage;

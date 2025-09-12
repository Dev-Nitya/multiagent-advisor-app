import React, { useState, useEffect, useMemo } from 'react';
import costService from '../services/costService';
import Navigation from './Navigation';
import SimpleChart from './SimpleChart';
import './CostDashboard.css';
import './SimpleChart.css';

const CostDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [modelData, setModelData] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('total_spent_usd');
  const [filterBy, setFilterBy] = useState('all'); // 'all', specific provider, or model
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const modelResult = await costService.getCostByModel();

        if (modelResult.success) {
          setModelData(modelResult.data);
        }
      } catch (error) {
        console.error('Error fetching cost data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Calculate summary statistics
  const summaryStats = useMemo(() => {
    if (!modelData || modelData.length === 0) return null;

    const totalSpent = modelData.reduce((sum, item) => sum + (item.total_spent_usd || 0), 0);
    const totalTokens = modelData.reduce((sum, item) => sum + (item.prompt_tokens || 0) + (item.completion_tokens || 0), 0);
    const totalEvents = modelData.reduce((sum, item) => sum + (item.event_count || 0), 0);
    const avgCostPerEvent = totalEvents > 0 ? totalSpent / totalEvents : 0;

    return {
      totalSpent,
      totalTokens,
      totalEvents,
      avgCostPerEvent,
      itemCount: modelData.length
    };
  }, [modelData]);

  // Filter and sort data
  const filteredAndSortedData = useMemo(() => {
    let data = modelData;
    
    // Apply search filter
    if (searchTerm) {
      data = data.filter(item => {
        const searchFields = [item.model_name, item.provider];
        
        return searchFields.some(field => 
          field && field.toString().toLowerCase().includes(searchTerm.toLowerCase())
        );
      });
    }

    // Apply additional filters
    if (filterBy !== 'all') {
      data = data.filter(item => {
        return item.model_name === filterBy || item.provider === filterBy;
      });
    }

    // Sort data
    data.sort((a, b) => {
      const aVal = a[sortBy] || 0;
      const bVal = b[sortBy] || 0;
      return bVal - aVal; // Descending order
    });

    return data;
  }, [modelData, searchTerm, sortBy, filterBy]);

  // Pagination
  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return filteredAndSortedData.slice(startIndex, startIndex + itemsPerPage);
  }, [filteredAndSortedData, currentPage]);

  const totalPages = Math.ceil(filteredAndSortedData.length / itemsPerPage);

  // Get unique providers and models for filter dropdown
  const filterOptions = useMemo(() => {
    const providers = [...new Set(modelData.map(item => item.provider).filter(Boolean))];
    const models = [...new Set(modelData.map(item => item.model_name).filter(Boolean))];
    return [...providers, ...models];
  }, [modelData]);

  const handlePageChange = (page) => {
    setCurrentPage(page);
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 4
    }).format(amount);
  };

  const formatNumber = (num) => {
    return new Intl.NumberFormat('en-US').format(num);
  };

  if (loading) {
    return (
      <div className="cost-dashboard">
        <Navigation />
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Loading cost data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="cost-dashboard">
      <Navigation />
      <div className="cost-content">
        <div className="page-header">
          <h1>Cost Dashboard</h1>
          <p>Monitor and analyze AI model usage costs by model and provider</p>
        </div>

        {/* Summary Cards */}
        {summaryStats && (
          <div className="summary-cards">
            <div className="summary-card">
              <div className="summary-title">Total Spent</div>
              <div className="summary-value">{formatCurrency(summaryStats.totalSpent)}</div>
            </div>
            <div className="summary-card">
              <div className="summary-title">Total Tokens</div>
              <div className="summary-value">{formatNumber(summaryStats.totalTokens)}</div>
            </div>
            <div className="summary-card">
              <div className="summary-title">Total Events</div>
              <div className="summary-value">{formatNumber(summaryStats.totalEvents)}</div>
            </div>
            <div className="summary-card">
              <div className="summary-title">Avg Cost/Event</div>
              <div className="summary-value">{formatCurrency(summaryStats.avgCostPerEvent)}</div>
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="dashboard-controls">
          <div className="filters">
            <input
              type="text"
              placeholder="Search models..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              className="search-input"
            />

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="sort-select"
            >
              <option value="total_spent_usd">Sort by Total Cost</option>
              <option value="event_count">Sort by Event Count</option>
              <option value="prompt_tokens">Sort by Prompt Tokens</option>
              <option value="completion_tokens">Sort by Completion Tokens</option>
              <option value="avg_spent_usd">Sort by Avg Cost</option>
            </select>

            <select
              value={filterBy}
              onChange={(e) => {
                setFilterBy(e.target.value);
                setCurrentPage(1);
              }}
              className="filter-select"
            >
              <option value="all">All Models</option>
              {filterOptions.map(option => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Cost Charts */}
        <div className="charts-grid">
          <SimpleChart
            data={filteredAndSortedData.slice(0, 8)}
            valueKey="total_spent_usd"
            labelKey="model_name"
            title="Top Models by Total Cost"
            height={300}
          />
          <SimpleChart
            data={filteredAndSortedData.slice(0, 8)}
            valueKey="event_count"
            labelKey="model_name"
            title="Top Models by Usage Count"
            height={300}
          />
        </div>

        {/* Cost Visualization */}
        <div className="cost-visualization">
          <h3>Cost Distribution</h3>
          <div className="cost-bars">
            {paginatedData.slice(0, 5).map((item, index) => {
              const maxCost = Math.max(...filteredAndSortedData.map(d => d.total_spent_usd || 0));
              const widthPercentage = maxCost > 0 ? ((item.total_spent_usd || 0) / maxCost) * 100 : 0;
              
              return (
                <div key={item.model_name || index} className="cost-bar-item">
                  <div className="cost-bar-label">
                    {item.model_name}
                  </div>
                  <div className="cost-bar-container">
                    <div 
                      className="cost-bar-fill" 
                      style={{ width: `${widthPercentage}%` }}
                    ></div>
                    <span className="cost-bar-value">
                      {formatCurrency(item.total_spent_usd || 0)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Data Table */}
        <div className="cost-table-container">
          <table className="cost-table">
            <thead>
              <tr>
                <th>Model Name</th>
                <th>Provider</th>
                <th>Events</th>
                <th>Total Cost</th>
                <th>Avg Cost</th>
                <th>Tokens Used</th>
              </tr>
            </thead>
            <tbody>
              {paginatedData.map((item, index) => (
                <tr key={item.model_name || index}>
                  <td>
                    <span className="model-badge">{item.model_name || 'N/A'}</span>
                  </td>
                  <td>
                    <span className="provider-badge">{item.provider || 'N/A'}</span>
                  </td>
                  <td>{formatNumber(item.event_count || 0)}</td>
                  <td className="cost-cell">{formatCurrency(item.total_spent_usd || 0)}</td>
                  <td className="cost-cell">{formatCurrency(item.avg_spent_usd || 0)}</td>
                  <td>
                    <div className="token-breakdown">
                      <span>Input: {formatNumber(item.prompt_tokens || 0)}</span>
                      <span>Output: {formatNumber(item.completion_tokens || 0)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="pagination">
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
              className="pagination-btn"
            >
              Previous
            </button>
            
            <div className="page-numbers">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
                <button
                  key={page}
                  onClick={() => handlePageChange(page)}
                  className={`page-btn ${currentPage === page ? 'active' : ''}`}
                >
                  {page}
                </button>
              ))}
            </div>
            
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="pagination-btn"
            >
              Next
            </button>
          </div>
        )}

        <div className="data-summary">
          Showing {paginatedData.length} of {filteredAndSortedData.length} items
        </div>
      </div>
    </div>
  );
};

export default CostDashboard;

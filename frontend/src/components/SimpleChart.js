import React from 'react';

const SimpleChart = ({ data, valueKey, labelKey, title, height = 300 }) => {
  if (!data || data.length === 0) {
    return (
      <div className="chart-container" style={{ height }}>
        <h4>{title}</h4>
        <div className="no-data">No data available</div>
      </div>
    );
  }

  const maxValue = Math.max(...data.map(item => item[valueKey] || 0));
  const chartHeight = height - 60; // Account for title and labels

  return (
    <div className="chart-container" style={{ height }}>
      <h4 className="chart-title">{title}</h4>
      <div className="chart-area" style={{ height: chartHeight }}>
        <div className="chart-bars">
          {data.slice(0, 8).map((item, index) => {
            const value = item[valueKey] || 0;
            const barHeight = maxValue > 0 ? (value / maxValue) * (chartHeight - 40) : 0;
            
            return (
              <div key={index} className="chart-bar-group">
                <div className="chart-bar-container" style={{ height: chartHeight - 40 }}>
                  <div 
                    className="chart-bar"
                    style={{ 
                      height: `${barHeight}px`,
                      background: `linear-gradient(135deg, 
                        hsl(${200 + (index * 15)}, 70%, 60%), 
                        hsl(${210 + (index * 15)}, 70%, 70%))`
                    }}
                    title={`${item[labelKey]}: ${valueKey === 'total_spent_usd' ? '$' : ''}${value.toLocaleString()}`}
                  >
                    <span className="chart-bar-value">
                      {valueKey === 'total_spent_usd' ? '$' : ''}{value.toLocaleString()}
                    </span>
                  </div>
                </div>
                <div className="chart-bar-label">
                  {(item[labelKey] || '').toString().length > 12 
                    ? (item[labelKey] || '').toString().substring(0, 12) + '...'
                    : item[labelKey] || 'N/A'
                  }
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default SimpleChart;

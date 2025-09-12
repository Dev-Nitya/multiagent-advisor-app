import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const costService = {
  // Get cost breakdown by prompt
  getCostByPrompt: async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/cost-by-prompt`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching cost by prompt:', error);
      return {
        success: false,
        error: error.response?.data?.detail || error.message
      };
    }
  },

  // Get cost breakdown by model
  getCostByModel: async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/cost-by-model`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching cost by model:', error);
      return {
        success: false,
        error: error.response?.data?.detail || error.message
      };
    }
  }
};

export default costService;

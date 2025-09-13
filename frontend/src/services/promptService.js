import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const promptService = {
  // Get all prompts
  async getAllPrompts() {
    try {
      const response = await axios.get(`${API_BASE_URL}/prompts`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching prompts:', error);
      return {
        success: false,
        error: error.response?.data?.detail || 'Failed to fetch prompts'
      };
    }
  }
};

export default promptService;

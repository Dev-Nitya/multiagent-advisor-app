import axios from 'axios';

const promptService = {
  // Get all prompts
  async getAllPrompts() {
    try {
      const response = await axios.get('/prompts');
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

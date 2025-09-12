import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';

class AuthService {
  constructor() {
    this.token = localStorage.getItem('token');
    this.user = JSON.parse(localStorage.getItem('user') || 'null');
    this.setupInterceptors();
  }

  setupInterceptors() {
    // Add token to all requests
    axios.interceptors.request.use(
      (config) => {
        if (this.token) {
          config.headers.Authorization = `Bearer ${this.token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Handle authentication errors
    axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          this.logout();
        }
        return Promise.reject(error);
      }
    );
  }

  async register(userData) {
    try {
      const response = await axios.post('/auth/register', userData);
      const { access_token, user } = response.data;
      
      this.setAuth(access_token, user);
      return { success: true, user };
    } catch (error) {
      let errorMessage = 'Registration failed';
      
      if (error.response?.data) {
        // Handle different error formats
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail;
        } else if (Array.isArray(error.response.data.detail)) {
          // Handle Pydantic validation errors
          errorMessage = error.response.data.detail.map(err => 
            `${err.loc?.join(' ')}: ${err.msg}`
          ).join(', ');
        } else if (error.response.data.message) {
          errorMessage = error.response.data.message;
        }
      }
      
      return { 
        success: false, 
        error: errorMessage
      };
    }
  }

  async login(email, password) {
    try {
      const response = await axios.post('/auth/login', { email, password });
      const { access_token, user } = response.data;
      
      this.setAuth(access_token, user);
      return { success: true, user };
    } catch (error) {
      let errorMessage = 'Login failed';
      
      if (error.response?.data) {
        // Handle different error formats
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail;
        } else if (Array.isArray(error.response.data.detail)) {
          // Handle Pydantic validation errors
          errorMessage = error.response.data.detail.map(err => 
            `${err.loc?.join(' ')}: ${err.msg}`
          ).join(', ');
        } else if (error.response.data.message) {
          errorMessage = error.response.data.message;
        }
      }
      
      return { 
        success: false, 
        error: errorMessage
      };
    }
  }

  async getProfile() {
    try {
      const response = await axios.get('/auth/profile');
      this.user = response.data;
      localStorage.setItem('user', JSON.stringify(this.user));
      return { success: true, user: this.user };
    } catch (error) {
      let errorMessage = 'Failed to fetch profile';
      
      if (error.response?.data) {
        // Handle different error formats
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail;
        } else if (Array.isArray(error.response.data.detail)) {
          // Handle Pydantic validation errors
          errorMessage = error.response.data.detail.map(err => 
            `${err.loc?.join(' ')}: ${err.msg}`
          ).join(', ');
        } else if (error.response.data.message) {
          errorMessage = error.response.data.message;
        }
      }
      
      return { 
        success: false, 
        error: errorMessage
      };
    }
  }

  setAuth(token, user) {
    this.token = token;
    this.user = user;
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
  }

  logout() {
    this.token = null;
    this.user = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  }

  isAuthenticated() {
    return !!this.token && !!this.user;
  }

  getUser() {
    return this.user;
  }

  getToken() {
    return this.token;
  }

  // Prompt Sanitization methods
  async updatePromptSanitization(enabled) {
    try {
      const response = await axios.post(`/admin/users/${this.user.user_id}/prompt_sanitization`, {
        enabled: enabled
      });
      
      // Update local user data
      this.user.prompt_sanitization = enabled;
      localStorage.setItem('user', JSON.stringify(this.user));
      
      return { success: true, data: response.data };
    } catch (error) {
      let errorMessage = 'Failed to update prompt sanitization setting';
      
      if (error.response?.data) {
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail;
        } else if (typeof error.response.data === 'string') {
          errorMessage = error.response.data;
        }
      }
      
      return { success: false, error: errorMessage };
    }
  }

  async getPromptSanitization() {
    try {
      const response = await axios.get(`/admin/users/${this.user.user_id}/prompt_sanitization`);
      return { success: true, data: response.data };
    } catch (error) {
      let errorMessage = 'Failed to get prompt sanitization setting';
      
      if (error.response?.data) {
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail;
        } else if (typeof error.response.data === 'string') {
          errorMessage = error.response.data;
        }
      }
      
      return { success: false, error: errorMessage };
    }
  }
}

export default new AuthService();

import axios from 'axios';

// Base API configuration
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Don't redirect if using dev mode
      const devUser = localStorage.getItem('dev_user');
      if (!devUser) {
        // Token expired or invalid (real auth)
        localStorage.removeItem('access_token');
        window.location.href = '/login';
      }
      // In dev mode, just let the error pass through
    }
    return Promise.reject(error);
  }
);

export default api;

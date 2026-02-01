import axios from 'axios';

// Create axios instance with the base URL of your Flask server
const api = axios.create({
  baseURL: 'http://localhost:5000/api', 
  headers: {
    'Content-Type': 'application/json',
  },
});

// CRITICAL: This interceptor adds your JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token'); // Ensure this matches where you save the token on login
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const electionsAPI = {
  getAll: () => api.get('/elections'),
  getById: (id) => api.get(`/elections/${id}`),
  create: (data) => api.post('/elections', data),
  toggle: (id) => api.patch(`/elections/${id}/toggle`),
  addCandidate: (id, data) => api.post(`/elections/${id}/candidates`, data),
  hasVoted: (id) => api.get(`/elections/${id}/has-voted`),
};

export const adminAPI = {
  getUsers: () => api.get('/admin/users'),
  verifyVoter: (userId) => api.post(`/admin/users/${userId}/verify`),
};

export default api;
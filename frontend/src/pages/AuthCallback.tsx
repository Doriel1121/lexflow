import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

const AuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    // Extract token from URL query params
    const token = searchParams.get('token');
    
    if (token) {
      // Store token in localStorage
      localStorage.setItem('access_token', token);
      
      // Redirect to dashboard
      navigate('/');
      
      // Force a page reload to trigger AuthContext to fetch user info
      window.location.reload();
    } else {
      // No token found, redirect to login with error
      navigate('/login');
    }
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900">
      <div className="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-md">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Completing login...</h2>
        <div className="flex justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    </div>
  );
};

export default AuthCallback;

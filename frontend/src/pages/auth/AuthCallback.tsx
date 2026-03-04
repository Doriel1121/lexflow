import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const AuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refreshUser } = useAuth();

  useEffect(() => {
    const token = searchParams.get('token');

    if (token) {
      localStorage.setItem('access_token', token);
      // Trigger user fetch without page reload
      refreshUser().then(() => {
        navigate('/', { replace: true });
      }).catch(() => {
        navigate('/login', { replace: true });
      });
    } else {
      navigate('/login', { replace: true });
    }
  }, [searchParams, navigate, refreshUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="bg-white p-10 rounded-2xl shadow-xl border border-slate-100 flex flex-col items-center gap-4">
        <div className="h-12 w-12 rounded-full border-4 border-slate-200 border-t-blue-600 animate-spin" />
        <p className="text-slate-600 font-medium">Completing sign in...</p>
      </div>
    </div>
  );
};

export default AuthCallback;

import { useState } from 'react';
import { Scale, AlertCircle, Loader2, Mail, Lock, Building2, User } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Link, useNavigate } from 'react-router-dom';
import api from '../../services/api';

export default function Register() {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [formData, setFormData] = useState({
    organization_name: '',
    full_name: '',
    email: '',
    password: '',
    confirm_password: ''
  });

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (formData.password !== formData.confirm_password) {
      setError("Passwords do not match");
      return;
    }

    setIsLoading(true);
    try {
      // 1. Register the organization and user
      const response = await api.post('/v1/auth/register', {
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
        organization_name: formData.organization_name
      });
      
      // 2. Automatically log them in with the returned token
      localStorage.setItem('access_token', response.data.access_token);
      await refreshUser();
      
      // 3. Redirect to Dashboard
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden">
        
        <div className="bg-slate-900 p-8 text-center border-b border-slate-800">
          <div className="inline-flex items-center justify-center p-3 bg-white/10 rounded-xl mb-4 backdrop-blur-sm">
            <Scale className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-serif font-bold text-white tracking-tight">LexFlow</h1>
          <p className="text-slate-400 mt-1 text-sm font-medium">Create your workspace</p>
        </div>

        <div className="p-8">
          {error && (
            <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-600">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-4">
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Law Firm / Organization Name</label>
              <div className="relative">
                <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input 
                  type="text" 
                  required
                  value={formData.organization_name}
                  onChange={e => setFormData({...formData, organization_name: e.target.value})}
                  className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                  placeholder="Acme Legal Group"
                />
              </div>
            </div>

            <div className="relative pt-4">
              <div className="absolute inset-0 flex items-center pt-4">
                <span className="w-full border-t border-slate-100" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-white px-2 text-slate-400 font-medium tracking-wider uppercase">Admin Account</span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input 
                  type="text" 
                  required
                  value={formData.full_name}
                  onChange={e => setFormData({...formData, full_name: e.target.value})}
                  className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                  placeholder="Jane Doe"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Work Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input 
                  type="email" 
                  required
                  value={formData.email}
                  onChange={e => setFormData({...formData, email: e.target.value})}
                  className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                  placeholder="jane@acmelegal.com"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input 
                    type="password" 
                    required
                    minLength={8}
                    value={formData.password}
                    onChange={e => setFormData({...formData, password: e.target.value})}
                    className="w-full pl-9 pr-2 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                    placeholder="••••••••"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Confirm</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input 
                    type="password" 
                    required
                    value={formData.confirm_password}
                    onChange={e => setFormData({...formData, confirm_password: e.target.value})}
                    className="w-full pl-9 pr-2 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                    placeholder="••••••••"
                  />
                </div>
              </div>
            </div>

            <button 
              type="submit" 
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-2.5 mt-6 bg-slate-900 hover:bg-slate-800 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Create Workspace'}
            </button>
          </form>

          <div className="mt-8 text-center text-sm">
            <span className="text-slate-500">Already have a workspace? </span>
            <Link to="/login" className="text-slate-900 font-semibold hover:underline">
              Sign In
            </Link>
          </div>

        </div>
      </div>
    </div>
  );
}

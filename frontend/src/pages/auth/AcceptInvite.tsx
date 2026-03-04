import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { UserPlus, Loader2, KeyRound } from 'lucide-react';
import api from '../../services/api';

export default function AcceptInvite() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("Invalid invitation link. No token found in URL.");
    }
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      // Hit the backend accept-invite endpoint
      await api.post('/v1/invitations/accept', {
        token,
        password,
        full_name: fullName
      });

      // Redirect to login page with success message
      navigate('/login?message=Account created successfully. You can now log in.');
      
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg).join(', '));
      } else {
        setError('Failed to accept invitation. The link may have expired or is invalid.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center p-4">
        <div className="bg-white border text-center border-slate-200 rounded-2xl w-full max-w-md p-8 shadow-xl">
          <div className="h-12 w-12 bg-red-100 text-red-600 rounded-xl flex items-center justify-center mx-auto mb-4">
            <UserPlus className="h-6 w-6" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Invalid Link</h2>
          <p className="text-slate-500 mb-6">{error}</p>
          <button 
            onClick={() => navigate('/login')}
            className="w-full bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold py-3 rounded-xl transition-colors"
          >
            Return to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center p-4">
      <div className="bg-white border border-slate-200 rounded-2xl w-full max-w-md shadow-xl overflow-hidden">
        
        {/* Header */}
        <div className="p-8 pb-6 text-center border-b border-slate-100">
          <div className="h-14 w-14 bg-indigo-100 text-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4 rotate-3 shadow-inner">
            <UserPlus className="h-7 w-7" />
          </div>
          <h2 className="text-2xl font-serif font-bold text-slate-900">Join Your Team</h2>
          <p className="text-slate-500 mt-2">You've been invited to join the workspace. Setup your password below to gain access.</p>
        </div>

        {/* Form Body */}
        <div className="p-8 pt-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            
            {error && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 font-medium">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">Full Name</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <UserPlus className="h-5 w-5" />
                </div>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2.5 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-colors"
                  placeholder="John Doe"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">New Password</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <KeyRound className="h-5 w-5" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2.5 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-colors"
                  placeholder="At least 8 characters"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">Confirm Password</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <KeyRound className="h-5 w-5" />
                </div>
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2.5 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-colors"
                  placeholder="Repeat new password"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !password || !confirmPassword || !fullName}
              className="w-full flex items-center justify-center gap-2 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-indigo-600/20 mt-6"
            >
              {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Accept Invitation & Create Account'}
            </button>
            
          </form>
        </div>
      </div>
    </div>
  );
}

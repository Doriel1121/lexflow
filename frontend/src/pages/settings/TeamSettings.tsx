import { useEffect, useState } from 'react';
import { Users, Mail, UserPlus, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import api from '../../services/api';

interface TeamMember {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export default function TeamSettings() {
  const { t } = useTranslation();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('lawyer');
  const [isInviting, setIsInviting] = useState(false);
  const [inviteMessage, setInviteMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);

  useEffect(() => {
    fetchTeamMembers();
  }, []);

  const fetchTeamMembers = async () => {
    try {
      setLoading(true);
      // For now we fetch all users, in a real app this endpoint should be filtered to current_user.org_id
      const res = await api.get('/v1/users');
      setMembers(res.data);
    } catch (err) {
      console.error('Failed to load team', err);
    } finally {
      setLoading(false);
    }
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsInviting(true);
    setInviteMessage(null);
    try {
      await api.post('/v1/invitations', {
        email: inviteEmail,
        role: inviteRole
      });
      setInviteMessage({ type: 'success', text: `Invitation sent to ${inviteEmail}` });
      setInviteEmail('');
    } catch (err: any) {
      let errorMessage = 'Failed to send invitation';
      const detail = err.response?.data?.detail;
      
      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (Array.isArray(detail)) {
        errorMessage = detail.map((d: any) => d.msg).join(', ');
      } else if (err.message) {
        errorMessage = err.message;
      }

      setInviteMessage({ 
        type: 'error', 
        text: errorMessage 
      });
    } finally {
      setIsInviting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">{t('team.title')}</h1>
        <p className="text-muted-foreground mt-1">{t('team.subtitle')}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        
        {/* INVITE FORM */}
        <div className="md:col-span-1 space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
              <UserPlus className="h-5 w-5 text-purple-600" />
              {t('team.inviteTeammate')}
            </h2>
            
            <form onSubmit={handleInvite} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">{t('team.emailAddress')}</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input 
                    type="email" 
                    required
                    value={inviteEmail}
                    onChange={e => setInviteEmail(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                    placeholder="colleague@firm.com"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">{t('team.role')}</label>
                <select
                  value={inviteRole}
                  onChange={e => setInviteRole(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                >
                  <option value="lawyer">{t('team.roles.lawyer')}</option>
                  <option value="assistant">{t('team.roles.assistant')}</option>
                  <option value="viewer">{t('team.roles.viewer')}</option>
                  <option value="org_admin">{t('team.roles.orgAdmin')}</option>
                </select>
              </div>

              {inviteMessage && (
                <div className={`p-3 rounded-lg text-sm ${inviteMessage.type === 'success' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
                  {inviteMessage.text}
                </div>
              )}

              <button 
                type="submit" 
                disabled={isInviting || !inviteEmail}
                className="w-full flex items-center justify-center gap-2 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {isInviting ? <Loader2 className="h-4 w-4 animate-spin" /> : t('team.sendInvitation')}
              </button>
            </form>
          </div>
        </div>

        {/* TEAM DIRECTORY */}
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-2">
                <Users className="h-4 w-4" />
                {t('team.activeMembers')}
              </h2>
              <span className="bg-white px-2.5 py-1 rounded-full text-xs font-medium text-slate-600 border border-slate-200 shadow-sm">
                {t('team.usersCount', { count: members.length })}
              </span>
            </div>
            
            <div className="divide-y divide-slate-100">
              {loading ? (
                <div className="p-12 text-center text-slate-500 flex flex-col items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin mb-4 text-purple-600" />
                  {t('team.loading')}
                </div>
              ) : members.length === 0 ? (
                <div className="p-12 text-center text-slate-500">
                  {t('team.noMembers')}
                </div>
              ) : (
                members.map((member) => (
                  <div key={member.id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-full bg-gradient-to-br from-purple-100 to-blue-100 flex items-center justify-center font-bold text-purple-700 border border-purple-200">
                        {member.full_name ? member.full_name.charAt(0).toUpperCase() : member.email.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-semibold text-slate-800">{member.full_name || t('team.pendingUser')}</p>
                        <p className="text-sm text-slate-500">{member.email}</p>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                        {member.role.replace('_', ' ')}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

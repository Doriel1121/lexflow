import { useEffect, useState } from 'react';
import { Search, MoreVertical, UserPlus } from 'lucide-react';
import api from '../../../services/api';
import { cn } from '../../../lib/utils';

interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  organization_id: number | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

const roleColors: Record<string, string> = {
  admin: 'bg-purple-100 text-purple-700 border-purple-200',
  org_admin: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  lawyer: 'bg-blue-100 text-blue-700 border-blue-200',
  assistant: 'bg-green-100 text-green-700 border-green-200',
  viewer: 'bg-slate-100 text-slate-700 border-slate-200',
};

export default function AdminUsers() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const res = await api.get('/v1/admin/users');
      setUsers(res.data);
    } catch (err) {
      console.error('Failed to load users', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredUsers = users.filter(u => 
    (u.full_name || '').toLowerCase().includes(searchTerm.toLowerCase()) || 
    (u.email || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">Users & Roles</h1>
          <p className="text-muted-foreground mt-1">Manage global system access and permissions.</p>
        </div>
        <button className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg font-medium transition-colors">
          <UserPlus className="h-4 w-4" />
          Invite User
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by name or email..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
              <tr>
                <th className="px-6 py-3">User</th>
                <th className="px-6 py-3">Role</th>
                <th className="px-6 py-3">Tenant ID</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Joined</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center">
                      <div className="h-8 w-8 rounded-full border-4 border-slate-200 border-t-purple-600 animate-spin mb-4" />
                      Loading users...
                    </div>
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    No users found matching your search.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((user) => (
                  <tr key={user.id} className="hover:bg-slate-50 transition-colors group">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-semibold text-slate-800">{user.full_name || 'No Name Provided'}</span>
                        <span className="text-slate-500 text-xs">{user.email}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={cn(
                        "inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold border",
                        roleColors[user.role?.toLowerCase() || 'viewer'] || roleColors['viewer']
                      )}>
                        {user.is_superuser ? 'SUPERADMIN' : (user.role || 'UNASSIGNED').toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {user.organization_id ? (
                        <span className="font-mono text-xs text-slate-600 bg-slate-100 px-2 py-1 rounded">
                          ORG-{user.organization_id}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400 italic">Independent</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {user.is_active ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
                          <span className="h-1.5 w-1.5 rounded-full bg-slate-400"></span>
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-500">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors">
                        <MoreVertical className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

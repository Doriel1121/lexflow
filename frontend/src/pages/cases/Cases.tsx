import React, { useState, useEffect } from 'react';
import { Plus, Briefcase, Calendar, AlertCircle, Loader2, FolderOpen, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import { EntityVerification } from '../../components/cases/EntityVerification';

interface Case {
  id: number;
  title: string;
  description: string;
  status: string;
  client_id: number;
  created_at: string;
}

export default function Cases() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState({ title: '', description: '' });

  useEffect(() => {
    fetchCases();
  }, []);

  const fetchCases = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/v1/cases/');
      setCases(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load cases. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.post('/v1/cases/', formData);
      setShowCreateModal(false);
      setFormData({ title: '', description: '' });
      fetchCases();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create case. Please try again.');
    } finally {
      setCreating(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'open': return 'bg-green-100 text-green-700 border border-green-200';
      case 'pending': return 'bg-amber-100 text-amber-700 border border-amber-200';
      case 'closed': return 'bg-slate-100 text-slate-600 border border-slate-200';
      case 'in_progress': return 'bg-blue-100 text-blue-700 border border-blue-200';
      default: return 'bg-slate-100 text-slate-600 border border-slate-200';
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">Cases</h1>
          <p className="text-muted-foreground mt-1">Manage and track your legal cases</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center space-x-2 bg-primary text-primary-foreground px-4 py-2.5 rounded-xl hover:bg-primary/90 transition-colors shadow-sm font-medium"
        >
          <Plus className="h-4 w-4" />
          <span>New Case</span>
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center h-64 gap-3 text-slate-400">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span>Loading cases...</span>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-xl flex items-center gap-3 text-destructive text-sm max-w-md">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchCases}
            className="px-4 py-2 border border-slate-200 rounded-lg text-sm hover:bg-slate-50 transition-colors"
          >
            Try again
          </button>
        </div>
      ) : cases.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 gap-4 text-center">
          <div className="p-4 bg-slate-100 rounded-full">
            <FolderOpen className="h-8 w-8 text-slate-400" />
          </div>
          <div>
            <p className="font-semibold text-slate-700">No cases yet</p>
            <p className="text-sm text-slate-500 mt-1">Create your first case to get started</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Create First Case
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cases.map((caseItem) => (
            <div
              key={caseItem.id}
              className="bg-card border border-border rounded-xl p-6 hover:shadow-md hover:border-primary/30 transition-all duration-200 cursor-pointer group"
              onClick={() => navigate(`/cases/${caseItem.id}`)}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="p-2 bg-primary/10 rounded-lg group-hover:bg-primary/20 transition-colors">
                  <Briefcase className="h-5 w-5 text-primary" />
                </div>
                <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${getStatusColor(caseItem.status)}`}>
                  {caseItem.status.replace(/_/g, ' ')}
                </span>
              </div>
              <h3 className="font-bold text-slate-800 mb-2 group-hover:text-primary transition-colors">{caseItem.title}</h3>
              <p className="text-sm text-slate-500 mb-4 line-clamp-2">{caseItem.description}</p>
              <div className="flex items-center text-xs text-slate-400 gap-1">
                <Calendar className="h-3.5 w-3.5" />
                <span>{new Date(caseItem.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-md animate-in fade-in duration-200">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-slate-800">Create New Case</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </div>
            <form onSubmit={handleCreateCase} className="space-y-4">
              <EntityVerification 
                onVerified={(details) => {
                  setFormData(prev => ({
                    ...prev,
                    title: prev.title ? prev.title : `Case — ${details.name}`,
                    description: prev.description ? prev.description : (details.address ? `Entity Address: ${details.address}` : '')
                  }));
                }} 
              />
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Case Title</label>
                <input
                  type="text"
                  required
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="w-full px-3 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm"
                  placeholder="e.g., Contract Dispute — Acme Corp"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Description</label>
                <textarea
                  required
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm resize-none"
                  rows={3}
                  placeholder="Brief description of the case and key parties involved..."
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-medium hover:bg-slate-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="flex-1 px-4 py-2.5 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {creating ? 'Creating...' : 'Create Case'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

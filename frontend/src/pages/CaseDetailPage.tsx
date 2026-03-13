import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, Upload, FileText, Calendar, User, Plus, Loader2, X, 
  AlertCircle, Clock, CheckCircle2, Scale, FileSignature, Reply, 
  Gavel, ShieldAlert, Edit2, CheckCircle, Trash2 as TrashIcon, Sparkles
} from 'lucide-react';
import api from '../services/api';
import { Case } from '../types';

interface Deadline {
  id: number;
  deadline_date: string;
  deadline_type: string;
  title?: string;
  description: string;
  confidence_score: number;
  document_name?: string;
  is_completed: boolean;
  assignee_id?: number;
}

const CaseDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [noteContent, setNoteContent] = useState('');
  const [addingNote, setAddingNote] = useState(false);
  
  // Deadline state
  const [showDeadlineModal, setShowDeadlineModal] = useState(false);
  const [editingDeadline, setEditingDeadline] = useState<Deadline | null>(null);
  const [deadlineForm, setDeadlineForm] = useState({
    title: '',
    deadline_date: '',
    deadline_time: '09:00',
    deadline_type: 'other',
    description: '',
    assignee_id: ''
  });
  const [savingDeadline, setSavingDeadline] = useState(false);
  const [teamMembers, setTeamMembers] = useState<any[]>([]);

  useEffect(() => {
    if (!id) return;
    fetchCase();
    fetchTeamMembers();
  }, [id]);

  useEffect(() => {
    let interval: any;
    if (uploading && id) {
      interval = setInterval(() => { fetchCaseSilent(); }, 5000);
    }
    return () => { if (interval) clearInterval(interval); };
  }, [uploading, id]);

  const fetchCase = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/v1/cases/${id}`);
      setCaseData(response.data);
      setError(null);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Failed to load case');
    } finally {
      setLoading(false);
    }
  };

  const fetchCaseSilent = async () => {
    try {
      const response = await api.get(`/v1/cases/${id}`);
      const newData = response.data;
      setCaseData(newData);
      if (uploading) {
        const stillProcessing = newData.documents?.some((d: any) => 
          d.processing_status === 'PROCESSING' || d.processing_status === 'QUEUED'
        );
        if (!stillProcessing) setUploading(false);
      }
    } catch (e) { console.error("Silent refresh failed", e); }
  };

  const fetchTeamMembers = async () => {
    try {
      const meRes = await api.get('/v1/users/me');
      const orgId = meRes.data.organization_id;
      const membersRes = await api.get(`/v1/organizations/${orgId}/members`);
      setTeamMembers(membersRes.data);
    } catch (e) { console.error("Failed to fetch team members", e); }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('case_id', id);
    try {
      await api.post('/v1/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      fetchCase();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Upload failed');
      setUploading(false);
    }
  };

  const handleSaveDeadline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setSavingDeadline(true);
    try {
      const payload = {
        ...deadlineForm,
        case_id: parseInt(id),
        deadline_date: `${deadlineForm.deadline_date}T${deadlineForm.deadline_time}:00`,
        assignee_id: deadlineForm.assignee_id ? parseInt(deadlineForm.assignee_id) : null
      };
      if (editingDeadline) {
        await api.patch(`/v1/deadlines/${editingDeadline.id}`, payload);
      } else {
        await api.post('/v1/deadlines/', payload);
      }
      setShowDeadlineModal(false);
      setEditingDeadline(null);
      setDeadlineForm({ title: '', deadline_date: '', deadline_time: '09:00', deadline_type: 'other', description: '', assignee_id: '' });
      fetchCase();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to save deadline');
    } finally { setSavingDeadline(false); }
  };

  const toggleDeadlineComplete = async (deadline: Deadline) => {
    try {
      await api.patch(`/v1/deadlines/${deadline.id}`, { is_completed: !deadline.is_completed });
      fetchCase();
    } catch (e) { alert("Failed to update status"); }
  };

  const handleDeleteDeadline = async (deadlineId: number) => {
    if (!confirm("Are you sure you want to delete this deadline?")) return;
    try {
      await api.delete(`/v1/deadlines/${deadlineId}`);
      fetchCase();
    } catch (e) { alert("Failed to delete"); }
  };

  const openEditDeadline = (d: Deadline) => {
    const dateObj = new Date(d.deadline_date);
    setEditingDeadline(d);
    setDeadlineForm({
      title: d.title || '',
      deadline_date: dateObj.toISOString().split('T')[0],
      deadline_time: dateObj.toTimeString().split(' ')[0].substring(0, 5),
      deadline_type: d.deadline_type,
      description: d.description || '',
      assignee_id: d.assignee_id?.toString() || ''
    });
    setShowDeadlineModal(true);
  };

  const getDeadlineIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'hearing': return <Gavel className="h-4 w-4" />;
      case 'filing': return <FileSignature className="h-4 w-4" />;
      case 'response': return <Reply className="h-4 w-4" />;
      case 'appeal': return <Scale className="h-4 w-4" />;
      case 'statute_of_limitations': return <ShieldAlert className="h-4 w-4" />;
      default: return <Clock className="h-4 w-4" />;
    }
  };

  const getDeadlineColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'hearing': return 'bg-amber-100 text-amber-700 border-amber-200';
      case 'filing': return 'bg-blue-100 text-blue-700 border-blue-200';
      case 'response': return 'bg-indigo-100 text-indigo-700 border-indigo-200';
      case 'appeal': return 'bg-purple-100 text-purple-700 border-purple-200';
      case 'statute_of_limitations': return 'bg-red-100 text-red-700 border-red-200';
      default: return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64 gap-3 text-slate-400"><Loader2 className="h-6 w-6 animate-spin" /><span>Loading case details...</span></div>;
  if (error || !caseData) return <div className="p-8 text-center bg-red-50 text-red-600 rounded-xl border border-red-100"><AlertCircle className="h-12 w-12 mx-auto mb-4 opacity-50" /><h2 className="text-lg font-bold">Error Loading Case</h2><p className="mt-2">{error}</p><button onClick={() => navigate('/cases')} className="mt-6 px-4 py-2 bg-red-600 text-white rounded-lg">Back to Cases</button></div>;

  const deadlines = (caseData as any).deadlines || [];
  const pendingDeadlines = deadlines.filter((d: any) => !d.is_completed).sort((a: any, b: any) => new Date(a.deadline_date).getTime() - new Date(b.deadline_date).getTime());
  const completedDeadlines = deadlines.filter((d: any) => d.is_completed).sort((a: any, b: any) => new Date(b.deadline_date).getTime() - new Date(a.deadline_date).getTime());

  return (
    <div className="space-y-6 flex flex-col min-h-full">
      <div className="flex items-center justify-between">
        <button onClick={() => navigate('/cases')} className="flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors group"><ArrowLeft className="h-4 w-4 group-hover:-translate-x-1 transition-transform" /><span>Back to Cases</span></button>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full -mr-32 -mt-32 blur-3xl" />
        <div className="relative z-10">
          <div className="flex items-start justify-between mb-6">
            <div><div className="flex items-center gap-3 mb-2"><span className={`px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${caseData.status === 'OPEN' ? 'bg-green-100 text-green-700 border-green-200' : 'bg-slate-100 text-slate-600 border-slate-200'}`}>{caseData.status}</span><span className="text-slate-400 text-sm">Case #{caseData.id}</span></div><h1 className="text-4xl font-serif font-bold text-slate-900">{caseData.title}</h1><p className="text-slate-500 mt-2 max-w-2xl">{caseData.description}</p></div>
          </div>
          <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-100">
            <div className="flex items-center gap-2 text-sm"><Calendar className="h-4 w-4 text-slate-400" /><div><p className="text-slate-500 text-xs">Created</p><p className="font-medium text-slate-700">{new Date(caseData.created_at).toLocaleDateString()}</p></div></div>
            <div className="flex items-center gap-2 text-sm"><User className="h-4 w-4 text-slate-400" /><div><p className="text-slate-500 text-xs">Client</p><p className="font-medium text-slate-700">{caseData.client_id ? `Client #${caseData.client_id}` : 'Not assigned'}</p></div></div>
            <div className="flex items-center gap-2 text-sm"><FileText className="h-4 w-4 text-slate-400" /><div><p className="text-slate-500 text-xs">Documents</p><p className="font-medium text-slate-700">{caseData.documents?.length || 0} files</p></div></div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-xl font-semibold text-slate-800">Documents</h2><label className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors cursor-pointer"><Upload className="h-4 w-4" /><span>{uploading ? '...' : 'Upload'}</span><input type="file" onChange={handleFileSelect} className="hidden" accept=".pdf,.doc,.docx,image/*" disabled={uploading}/></label></div>
          {uploading && <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-xl flex items-center gap-3"><Loader2 className="h-4 w-4 animate-spin text-blue-600" /><span className="text-xs text-blue-700 font-medium">Processing with AI...</span></div>}
          {caseData.documents && caseData.documents.length > 0 ? (
            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">{caseData.documents.map((doc) => (<div key={doc.id} className="p-3 bg-slate-50 border border-slate-200 rounded-xl hover:border-primary/30 transition-all cursor-pointer group" onClick={() => navigate(`/documents/${doc.id}`)}><div className="flex items-start gap-3"><div className="p-2 bg-white border border-slate-200 rounded-lg group-hover:border-primary/20 transition-colors"><FileText className="h-4 w-4 text-primary" /></div><div className="flex-1 min-w-0"><p className="font-semibold text-slate-800 text-sm truncate">{doc.filename}</p><div className="flex items-center gap-2 mt-1"><span className="text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded font-medium">{doc.classification || 'Doc'}</span><span className="text-[10px] text-slate-400">{doc.language?.toUpperCase() || 'EN'}</span></div></div></div></div>))}</div>
          ) : (<div className="flex flex-col items-center justify-center py-12 text-center text-slate-400"><FileText className="h-8 w-8 mb-2 opacity-20" /><p className="text-xs">No documents</p></div>)}
        </div>

        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-xl font-semibold text-slate-800 flex items-center gap-2">Timeline <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full font-bold">{pendingDeadlines.length}</span></h2><button onClick={() => setShowDeadlineModal(true)} className="p-1.5 bg-primary/10 text-primary rounded-lg hover:bg-primary/20 transition-colors"><Plus className="h-4 w-4" /></button></div>
          <div className="space-y-0 relative max-h-[500px] overflow-y-auto pr-2">
            {pendingDeadlines.length > 0 ? (
              <div className="relative pl-8">
                <div className="absolute left-3 top-2 bottom-2 w-0.5 bg-slate-100" />
                {pendingDeadlines.map((deadline: any) => (
                  <div key={deadline.id} className="relative pb-6 group">
                    <div className={`absolute -left-[26px] top-1 h-3.5 w-3.5 rounded-full border-2 border-white shadow-sm z-10 transition-transform group-hover:scale-125 ${new Date(deadline.deadline_date) < new Date() ? 'bg-red-500' : 'bg-primary'}`} />
                    <div className="p-3 bg-white border border-slate-100 rounded-xl hover:border-primary/20 hover:shadow-sm transition-all group">
                      <div className="flex items-center justify-between mb-2">
                        <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 border ${getDeadlineColor(deadline.deadline_type)}`}>{getDeadlineIcon(deadline.deadline_type)}{deadline.deadline_type.replace('_', ' ')}</span>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={() => openEditDeadline(deadline)} className="p-1 text-slate-400 hover:text-primary"><Edit2 className="h-3 w-3" /></button>
                          <button onClick={() => toggleDeadlineComplete(deadline)} className="p-1 text-slate-400 hover:text-green-600"><CheckCircle className="h-3 w-3" /></button>
                          <button onClick={() => handleDeleteDeadline(deadline.id)} className="p-1 text-slate-400 hover:text-red-600"><TrashIcon className="h-3 w-3" /></button>
                        </div>
                      </div>
                      <p className="text-sm font-bold text-slate-800">{deadline.title || new Date(deadline.deadline_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</p>
                      <p className="text-xs text-slate-500 mt-1 line-clamp-2">{deadline.description}</p>
                      <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-50">
                        <span className="text-[10px] text-slate-400 font-mono">{new Date(deadline.deadline_date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                        {deadline.document_name && <div className="flex items-center gap-1 text-[9px] text-slate-400 truncate max-w-[100px]"><FileText className="h-2.5 w-2.5" />{deadline.document_name}</div>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (<div className="text-center py-8 text-slate-400 text-xs"><Calendar className="h-8 w-8 mx-auto mb-2 opacity-20" />No upcoming deadlines</div>)}
            
            {completedDeadlines.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-100">
                <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Completed</h3>
                <div className="space-y-2">
                  {completedDeadlines.map((d: any) => (
                    <div key={d.id} className="p-2 bg-slate-50 rounded-lg border border-slate-100 flex items-center justify-between opacity-60">
                      <div className="flex items-center gap-3">
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        <div><p className="text-xs font-semibold text-slate-700 line-through">{d.title || d.deadline_type}</p><p className="text-[9px] text-slate-400">{new Date(d.deadline_date).toLocaleDateString()}</p></div>
                      </div>
                      <button onClick={() => toggleDeadlineComplete(d)} className="text-[10px] text-primary hover:underline">Undo</button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-xl font-semibold text-slate-800">Notes</h2><button onClick={() => setShowNoteModal(true)} className="flex items-center gap-2 px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-200 transition-colors"><Plus className="h-4 w-4" />Add</button></div>
          {caseData.notes && caseData.notes.length > 0 ? (
            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">{caseData.notes.sort((a,b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).map((note) => (<div key={note.id} className="p-3 bg-white border border-slate-100 rounded-xl shadow-sm"><p className="text-sm text-slate-700 whitespace-pre-wrap">{note.content}</p><div className="flex items-center gap-2 mt-2 pt-2 border-t border-slate-50"><User className="h-3 w-3 text-slate-300" /><span className="text-[10px] text-slate-400 font-medium">{new Date(note.created_at).toLocaleDateString()} at {new Date(note.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span></div></div>))}</div>
          ) : (<div className="flex flex-col items-center justify-center py-12 text-center text-slate-400"><Plus className="h-8 w-8 mb-2 opacity-20" /><p className="text-xs">No case notes</p></div>)}
        </div>
      </div>

      {/* Deadline Modal */}
      {showDeadlineModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden animate-in zoom-in duration-200">
            <div className="p-6 border-b border-slate-100 flex items-center justify-between">
              <h3 className="text-xl font-bold text-slate-800">{editingDeadline ? 'Edit Deadline' : 'Add New Deadline'}</h3>
              <button onClick={() => { setShowDeadlineModal(false); setEditingDeadline(null); }} className="text-slate-400 hover:text-slate-600"><X className="h-5 w-5" /></button>
            </div>
            <form onSubmit={handleSaveDeadline} className="p-6 space-y-4">
              <div><label className="block text-xs font-bold text-slate-500 uppercase mb-1">Title</label><input type="text" required value={deadlineForm.title} onChange={e => setDeadlineForm({...deadlineForm, title: e.target.value})} className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary/20 outline-none transition-all" placeholder="e.g., File Statement of Defense" /></div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-xs font-bold text-slate-500 uppercase mb-1">Date</label><input type="date" required value={deadlineForm.deadline_date} onChange={e => setDeadlineForm({...deadlineForm, deadline_date: e.target.value})} className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl outline-none" /></div>
                <div><label className="block text-xs font-bold text-slate-500 uppercase mb-1">Time</label><input type="time" required value={deadlineForm.deadline_time} onChange={e => setDeadlineForm({...deadlineForm, deadline_time: e.target.value})} className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl outline-none" /></div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-xs font-bold text-slate-500 uppercase mb-1">Type</label><select value={deadlineForm.deadline_type} onChange={e => setDeadlineForm({...deadlineForm, deadline_type: e.target.value})} className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl outline-none"><option value="hearing">Hearing</option><option value="filing">Filing</option><option value="response">Response</option><option value="appeal">Appeal</option><option value="statute_of_limitations">Statute of Limitations</option><option value="other">Other</option></select></div>
                <div><label className="block text-xs font-bold text-slate-500 uppercase mb-1">Assignee</label><select value={deadlineForm.assignee_id} onChange={e => setDeadlineForm({...deadlineForm, assignee_id: e.target.value})} className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl outline-none"><option value="">Unassigned</option>{teamMembers.map(m => <option key={m.id} value={m.id}>{m.full_name}</option>)}</select></div>
              </div>
              <div><label className="block text-xs font-bold text-slate-500 uppercase mb-1">Description</label><textarea rows={3} value={deadlineForm.description} onChange={e => setDeadlineForm({...deadlineForm, description: e.target.value})} className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl outline-none resize-none" placeholder="Additional details..." /></div>
              <div className="pt-4 flex gap-3"><button type="button" onClick={() => { setShowDeadlineModal(false); setEditingDeadline(null); }} className="flex-1 px-4 py-3 bg-slate-100 text-slate-600 rounded-xl font-bold hover:bg-slate-200 transition-colors">Cancel</button><button type="submit" disabled={savingDeadline} className="flex-1 px-4 py-3 bg-primary text-white rounded-xl font-bold hover:bg-primary/90 transition-all flex items-center justify-center gap-2">{savingDeadline && <Loader2 className="h-4 w-4 animate-spin" />}{editingDeadline ? 'Update Deadline' : 'Create Deadline'}</button></div>
            </form>
          </div>
        </div>
      )}

      {/* Note Modal */}
      {showNoteModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in zoom-in duration-200">
            <div className="p-6 border-b border-slate-100 flex items-center justify-between"><h3 className="text-xl font-bold text-slate-800">Add Case Note</h3><button onClick={() => setShowNoteModal(false)} className="text-slate-400 hover:text-slate-600"><X className="h-5 w-5" /></button></div>
            <div className="p-6"><textarea rows={5} value={noteContent} onChange={(e) => setNoteContent(e.target.value)} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary/20 outline-none transition-all resize-none mb-4" placeholder="Enter note content..." /><div className="flex gap-3"><button onClick={() => setShowNoteModal(false)} className="flex-1 px-4 py-2 bg-slate-100 text-slate-600 rounded-xl font-bold hover:bg-slate-200 transition-colors">Cancel</button><button onClick={handleAddNote} disabled={addingNote} className="flex-1 px-4 py-2 bg-primary text-white rounded-xl font-bold hover:bg-primary/90 transition-all flex items-center justify-center gap-2">{addingNote && <Loader2 className="h-4 w-4 animate-spin" />}Add Note</button></div></div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CaseDetailPage;

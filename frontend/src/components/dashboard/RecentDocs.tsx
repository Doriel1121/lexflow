import { useEffect, useState } from 'react';
import { FileText, MoreVertical } from 'lucide-react';
import api from '../../services/api';

interface Document {
  id: number;
  filename: string;
  case_id: number;
  classification: string;
  created_at: string;
}

export function RecentDocs() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRecentDocs();
  }, []);

  const fetchRecentDocs = async () => {
    try {
      const response = await api.get('/v1/documents/recent?limit=5');
      setDocuments(response.data);
    } catch (error) {
      console.error('Failed to fetch recent documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours} hrs ago`;
    if (diffDays === 1) return '1 day ago';
    return `${diffDays} days ago`;
  };
  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
      <div className="p-6 border-b border-border flex justify-between items-center">
        <h3 className="font-serif font-bold text-slate-800">Recent Documents</h3>
        <button className="text-sm text-primary font-medium hover:underline">View All</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-muted/50 text-muted-foreground font-medium border-b border-border">
            <tr>
              <th className="px-6 py-3">Document Name</th>
              <th className="px-6 py-3">Case Reference</th>
              <th className="px-6 py-3">Uploaded</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                  Loading documents...
                </td>
              </tr>
            ) : documents.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                  No documents yet
                </td>
              </tr>
            ) : (
              documents.map((doc) => (
              <tr key={doc.id} className="hover:bg-muted/30 transition-colors group">
                <td className="px-6 py-4">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-slate-100 rounded text-slate-500">
                      <FileText className="h-4 w-4" />
                    </div>
                    <span className="font-medium text-slate-700 group-hover:text-primary transition-colors">{doc.filename}</span>
                  </div>
                </td>
                <td className="px-6 py-4 text-slate-600">Case #{doc.case_id}</td>
                <td className="px-6 py-4 text-slate-500">{formatDate(doc.created_at)}</td>
                <td className="px-6 py-4">
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                    {doc.classification || 'Processed'}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  <button className="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600">
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
  );
}

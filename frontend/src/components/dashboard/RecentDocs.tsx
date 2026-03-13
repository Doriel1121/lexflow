import { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import api from "../../services/api";

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
      const response = await api.get("/v1/documents/recent?limit=5");
      setDocuments(response.data);
    } catch (error) {
      console.error("Failed to fetch recent documents:", error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "Unknown";
    const utcDateStr = dateStr.endsWith("Z") ? dateStr : `${dateStr}Z`;
    const date = new Date(utcDateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffHours < 1) return "Just now";
    if (diffHours < 24) return `${diffHours} hrs ago`;
    if (diffDays === 1) return "1 day ago";
    return `${diffDays} days ago`;
  };
  return (
    <div className="bg-white rounded-2xl overflow-hidden">
      <div className="px-5 py-4 flex justify-between items-center">
        <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wide">
          Recent Documents
        </h3>
        <a
          href="/documents"
          className="text-xs text-slate-400 hover:text-slate-600 font-medium transition-colors"
        >
          View all →
        </a>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="border-t border-b border-slate-50">
              <th className="px-5 py-2.5 text-xs font-semibold text-slate-400 uppercase text-start tracking-wider">
                Document
              </th>
              <th className="px-5 py-2.5 text-xs font-semibold text-slate-400 uppercase text-start tracking-wider">
                Case
              </th>
              <th className="px-5 py-2.5 text-xs font-semibold text-slate-400 uppercase text-start tracking-wider">
                Uploaded
              </th>
              <th className="px-5 py-2.5 text-xs font-semibold text-slate-400 uppercase text-start tracking-wider">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {loading ? (
              <tr>
                <td
                  colSpan={4}
                  className="px-5 py-8 text-center text-slate-400 text-sm"
                >
                  <div className="flex items-center justify-center gap-2">
                    <div className="h-4 w-4 rounded-full border-2 border-slate-200 border-t-slate-400 animate-spin" />
                    Loading...
                  </div>
                </td>
              </tr>
            ) : documents.length === 0 ? (
              <tr>
                <td
                  colSpan={4}
                  className="px-5 py-10 text-center text-slate-400 text-sm"
                >
                  No documents uploaded yet.
                </td>
              </tr>
            ) : (
              documents.map((doc) => (
                <tr
                  key={doc.id}
                  className="hover:bg-slate-50/60 transition-colors group"
                >
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="p-1.5 bg-slate-100 rounded-lg text-slate-400 shrink-0">
                        <FileText className="h-3.5 w-3.5" />
                      </div>
                      <span className="font-medium text-slate-700 truncate max-w-[180px] group-hover:text-blue-600 transition-colors">
                        {doc.filename}
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-slate-500 text-xs">
                    Case #{doc.case_id}
                  </td>
                  <td className="px-5 py-3.5 text-slate-400 text-xs">
                    {formatDate(doc.created_at)}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-600">
                      {doc.classification || "Processed"}
                    </span>
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

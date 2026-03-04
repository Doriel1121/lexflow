import { useEffect, useState } from 'react';
import api from '../services/api';
import { Document } from '../types';

const DocumentsPage: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [modalContent, setModalContent] = useState<{title: string, content: string} | null>(null);
  const [processing, setProcessing] = useState<number | null>(null);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const response = await api.get('/v1/documents/');
      setDocuments(response.data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch documents');
    } finally {
      setLoading(false);
    }
  };

  const viewFullText = async (docId: number) => {
    setProcessing(docId);
    try {
      const response = await api.get(`/v1/documents/${docId}/text`);
      const data = response.data;
      setModalContent({
        title: `Full Text: ${data.filename}`,
        content: `Language: ${data.language}\nPages: ${data.page_count}\n\n${data.content}`
      });
    } catch (error: any) {
      alert(`Failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setProcessing(null);
    }
  };

  const viewMetadata = async (docId: number) => {
    setProcessing(docId);
    try {
      let metadata;
      try {
        const response = await api.get(`/v1/documents/${docId}/metadata`);
        metadata = response.data;
      } catch {
        const response = await api.post(`/v1/documents/${docId}/extract-metadata`);
        metadata = response.data;
      }
      
      const content = `📅 Dates: ${metadata.dates?.length || 0}\n${metadata.dates?.join('\n') || 'None'}\n\n👥 Entities: ${metadata.entities?.length || 0}\n${metadata.entities?.join('\n') || 'None'}\n\n💰 Amounts: ${metadata.amounts?.length || 0}\n${metadata.amounts?.join('\n') || 'None'}\n\n📋 Case Numbers: ${metadata.case_numbers?.length || 0}\n${metadata.case_numbers?.join('\n') || 'None'}`;
      
      setModalContent({
        title: 'Extracted Metadata',
        content
      });
    } catch (error: any) {
      alert(`Failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setProcessing(null);
    }
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') return '📄';
    if (['doc', 'docx'].includes(ext || '')) return '📝';
    if (['jpg', 'jpeg', 'png'].includes(ext || '')) return '🖼️';
    if (['txt', 'md'].includes(ext || '')) return '📃';
    return '📎';
  };

  if (loading) return <div className="p-4">Loading documents...</div>;

  return (
    <div className="p-4">
      <h1 className="text-3xl font-bold mb-4">All Documents</h1>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          <strong>Error:</strong> {error}
        </div>
      )}

      {documents.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 text-center">
          <p className="text-gray-600 dark:text-gray-400">No documents found. Upload documents from case pages.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {documents.map((doc) => (
            <div key={doc.id} className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 hover:shadow-lg transition-shadow">
              <div className="flex items-start gap-3">
                <span className="text-4xl">{getFileIcon(doc.filename)}</span>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 dark:text-white truncate">{doc.filename}</h3>
                  <p className="text-xs text-gray-500 mt-1">Case #{doc.case_id}</p>
                  <p className="text-xs text-gray-500">
                    {doc.classification || 'Unclassified'} • {doc.language || 'en'} • {doc.page_count || 0} pages
                  </p>
                  <div className="mt-3 flex gap-1 flex-wrap">
                    <button
                      onClick={() => viewFullText(doc.id)}
                      disabled={processing === doc.id}
                      className="px-2 py-1 bg-purple-600 text-white text-xs rounded hover:bg-purple-700 disabled:opacity-50"
                    >
                      {processing === doc.id ? '⏳' : '📄 Text'}
                    </button>
                    <button
                      onClick={() => viewMetadata(doc.id)}
                      disabled={processing === doc.id}
                      className="px-2 py-1 bg-orange-600 text-white text-xs rounded hover:bg-orange-700 disabled:opacity-50"
                    >
                      {processing === doc.id ? '⏳' : '🔍 Meta'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Document Viewer Modal */}
      {selectedDoc && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setSelectedDoc(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold">{getFileIcon(selectedDoc.filename)} {selectedDoc.filename}</h2>
                <p className="text-sm text-gray-500">Case #{selectedDoc.case_id} • {selectedDoc.classification}</p>
              </div>
              <button onClick={() => setSelectedDoc(null)} className="text-gray-500 hover:text-gray-700 text-3xl">&times;</button>
            </div>
            <div className="p-6 overflow-y-auto max-h-[70vh]">
              {selectedDoc.content ? (
                <pre className="whitespace-pre-wrap text-sm font-mono bg-gray-50 dark:bg-gray-900 p-4 rounded">{selectedDoc.content}</pre>
              ) : (
                <div className="text-center text-gray-500 py-8">
                  <p>No content extracted yet.</p>
                  <p className="text-sm mt-2">Go to the case page and click "View Content" to extract text.</p>
                </div>
              )}
            </div>
            <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-2">
              <button onClick={() => setSelectedDoc(null)} className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Metadata/Text Modal */}
      {modalContent && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setModalContent(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
              <h2 className="text-2xl font-bold">{modalContent.title}</h2>
              <button onClick={() => setModalContent(null)} className="text-gray-500 hover:text-gray-700 text-3xl">&times;</button>
            </div>
            <div className="p-6 overflow-y-auto max-h-[70vh]">
              <pre className="whitespace-pre-wrap text-sm font-mono bg-gray-50 dark:bg-gray-900 p-4 rounded">{modalContent.content}</pre>
            </div>
            <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <button onClick={() => setModalContent(null)} className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700">Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentsPage;

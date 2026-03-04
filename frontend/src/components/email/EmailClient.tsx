import { useState, useEffect } from 'react';
import { Mail, RefreshCw, Paperclip, ArrowRight, UserPlus, FolderPlus, Inbox, Archive, Trash2, Search } from 'lucide-react';
import { cn } from '../../lib/utils';
import api from '../../services/api';

interface Email {
  id: number;
  from: string;
  subject: string;
  text: string;
  date: string;
  unread: boolean;
  attachments: string[];
}

export function EmailClient() {
  const [emails, setEmails] = useState<Email[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchEmails();
  }, []);

  const fetchEmails = async () => {
    setLoading(true);
    try {
      const response = await api.get('/v1/email/messages');
      setEmails(response.data);
    } catch (error) {
      console.error('Failed to fetch emails:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    try {
      // Use simplified Gmail OAuth sync
      await api.post('/v1/email/sync-gmail');
      alert('Emails synced successfully!');
      setTimeout(fetchEmails, 2000);
    } catch (error: any) {
      if (error.response?.status === 400) {
        alert('Please login with Google to sync emails');
      } else if (error.response?.status === 401) {
        alert('Gmail access expired. Please login again.');
      } else {
        alert(`Sync failed: ${error.response?.data?.detail || error.message}`);
      }
    }
  };

  const activeEmail = emails.find(e => e.id === selectedEmail);

  return (
    <div className="flex h-[calc(100vh-8rem)] bg-card border border-border rounded-xl shadow-sm overflow-hidden">
      {/* 1. Left Sidebar: Inboxes */}
      <div className="w-64 bg-slate-50 border-r border-border flex flex-col">
        <div className="p-4 border-b border-border">
          <button 
            onClick={handleSync}
            className="w-full flex items-center justify-center space-x-2 bg-white border border-border hover:bg-slate-50 text-slate-700 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm"
          >
            <RefreshCw className="h-4 w-4" />
            <span>Sync Inboxes</span>
          </button>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          <button className="w-full flex items-center justify-between px-3 py-2 bg-white shadow-sm border border-slate-200 rounded-lg text-sm font-medium text-slate-900">
            <div className="flex items-center space-x-3">
              <Inbox className="h-4 w-4 text-primary" />
              <span>Intake</span>
            </div>
            <span className="bg-primary text-primary-foreground px-2 py-0.5 rounded-full text-xs">{emails.length}</span>
          </button>
          <button className="w-full flex items-center justify-between px-3 py-2 hover:bg-slate-100 rounded-lg text-sm font-medium text-slate-600 transition-colors">
            <div className="flex items-center space-x-3">
              <Archive className="h-4 w-4" />
              <span>Processed</span>
            </div>
          </button>
          <button className="w-full flex items-center justify-between px-3 py-2 hover:bg-slate-100 rounded-lg text-sm font-medium text-slate-600 transition-colors">
            <div className="flex items-center space-x-3">
              <Trash2 className="h-4 w-4" />
              <span>Trash</span>
            </div>
          </button>
        </nav>
        <div className="p-4 bg-slate-100 border-t border-border">
           <p className="text-xs text-slate-500 font-medium mb-2">Gmail Connected</p>
           <p className="text-xs text-slate-600">Login with Google to sync</p>
        </div>
      </div>

      {/* 2. Middle Pane: Email List */}
      <div className="w-80 border-r border-border flex flex-col bg-white">
        <div className="p-4 border-b border-border">
          <div className="relative">
             <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
             <input type="text" placeholder="Search mail..." className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-primary" />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-gray-500">Loading emails...</div>
          ) : emails.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              <p>No emails yet.</p>
              <p className="text-sm mt-2">Click "Sync Inboxes" to fetch emails.</p>
            </div>
          ) : (
            emails.map(email => (
              <div 
                key={email.id}
                onClick={() => setSelectedEmail(email.id)}
                className={cn(
                  "p-4 border-b border-slate-100 cursor-pointer hover:bg-slate-50 transition-colors",
                  selectedEmail === email.id ? "bg-blue-50/50 border-l-4 border-l-primary" : "border-l-4 border-l-transparent",
                  email.unread ? "bg-slate-50" : "bg-white"
                )}
              >
                <div className="flex justify-between items-start mb-1">
                  <span className={cn("text-sm font-medium truncate pr-2", email.unread ? "text-slate-900 font-bold" : "text-slate-700")}>{email.from}</span>
                  <span className="text-xs text-slate-400 whitespace-nowrap">{email.date}</span>
                </div>
                <p className={cn("text-sm mb-1 truncate", email.unread ? "font-semibold text-slate-800" : "text-slate-600")}>{email.subject}</p>
                <p className="text-xs text-slate-500 truncate">{email.text}</p>
                {email.attachments.length > 0 && (
                  <div className="mt-2 flex items-center space-x-2">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                      <Paperclip className="h-3 w-3 mr-1" />
                      {email.attachments.length}
                    </span>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* 3. Right Pane: Preview & Actions */}
      <div className="flex-1 flex flex-col bg-white">
        {activeEmail ? (
          <>
            <div className="p-6 border-b border-border">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 mb-2">{activeEmail.subject}</h2>
                  <div className="flex items-center space-x-2 text-sm text-slate-600">
                    <span className="font-medium text-slate-900">{activeEmail.from}</span>
                    <span className="text-slate-400">to</span>
                    <span>Me</span>
                  </div>
                </div>
                <span className="text-sm text-slate-500">{activeEmail.date}</span>
              </div>

              {/* Action Toolbar */}
              <div className="flex space-x-3">
                <button className="flex items-center space-x-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors shadow-sm">
                  <FolderPlus className="h-4 w-4" />
                  <span>Attach to Case</span>
                </button>
                <button className="flex items-center space-x-2 px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors shadow-sm">
                  <UserPlus className="h-4 w-4" />
                  <span>Create Client</span>
                </button>
              </div>
            </div>

            <div className="flex-1 p-8 overflow-y-auto">
              <div className="prose prose-sm max-w-none text-slate-700">
                <p className="mb-4">Dear Counsel,</p>
                <p className="mb-4">{activeEmail.text}</p>
                <p>Best regards,</p>
                <p>Sender Signature</p>
              </div>

              {activeEmail.attachments.length > 0 && (
                <div className="mt-8 border-t border-slate-100 pt-6">
                  <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center">
                    <Paperclip className="h-4 w-4 mr-2" />
                    Attachments ({activeEmail.attachments.length})
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    {activeEmail.attachments.map((file, i) => (
                      <div key={i} className="flex items-center justify-between p-3 border border-slate-200 rounded-lg hover:bg-slate-50 cursor-pointer group transition-colors">
                        <div className="flex items-center space-x-3">
                          <div className="p-2 bg-red-100 rounded text-red-600">
                            <ArrowRight className="h-4 w-4 -rotate-45" />
                          </div>
                          <span className="text-sm font-medium text-slate-700">{file}</span>
                        </div>
                        <button className="text-primary text-xs font-medium hover:underline opacity-0 group-hover:opacity-100 transition-opacity">
                          Preview
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8 text-center">
            <div className="bg-slate-100 p-4 rounded-full mb-4">
              <Mail className="h-8 w-8 text-slate-400" />
            </div>
            <h3 className="text-lg font-medium text-slate-800">No emails loaded</h3>
            <p className="max-w-xs mt-2 text-sm">Click "Sync Inboxes" to fetch emails from your configured accounts.</p>
          </div>
        )}
      </div>
    </div>
  );
}

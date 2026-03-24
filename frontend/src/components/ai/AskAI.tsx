import React, { useState, useRef, useEffect } from 'react';
import { Bot, Send, Loader2, X, Sparkles, User as UserIcon } from 'lucide-react';
import aiService from '../../services/ai';
import { Citation } from '../../types';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  error?: boolean;
}

interface AskAIProps {
  caseId?: number;
  documentIds?: number[];
  title?: string;
}

const AskAI: React.FC<AskAIProps> = ({ caseId, documentIds, title = "Ask AI about this Case" }) => {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;

    const userQuestion = question.trim();
    const messageId = Date.now().toString();
    
    // Add user message and clear input
    setMessages(prev => [...prev, { id: messageId, role: 'user', content: userQuestion }]);
    setQuestion('');
    setIsLoading(true);

    try {
      const res = await aiService.askAI({
        question: userQuestion,
        case_id: caseId,
        document_ids: documentIds,
        top_k: 8,
      });

      setMessages(prev => [...prev, { 
        id: (Date.now() + 1).toString(), 
        role: 'assistant', 
        content: res.answer,
        citations: res.citations 
      }]);
    } catch (err: any) {
      console.error("Ask AI failed:", err);
      setMessages(prev => [...prev, { 
        id: (Date.now() + 1).toString(), 
        role: 'assistant', 
        content: err.response?.data?.detail || "An unexpected error occurred. Please try again.",
        error: true
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearHistory = () => {
    setMessages([]);
    setIsFocused(false);
  };

  const hasHistory = messages.length > 0;

  return (
    <div className={`bg-white border border-primary-100 rounded-2xl shadow-sm transition-all duration-300 overflow-hidden flex flex-col ${isFocused || hasHistory ? 'ring-2 ring-primary-500/10' : 'hover:border-primary-200'}`}>
      {/* Header */}
      {(hasHistory || isFocused) && (
        <div className="px-4 py-3 border-b border-slate-50 flex items-center justify-between bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-primary-600" />
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{title}</span>
          </div>
          {hasHistory && (
            <button 
              onClick={clearHistory}
              className="text-[10px] font-bold text-slate-400 hover:text-red-500 uppercase tracking-tight transition-colors flex items-center gap-1"
            >
              <X className="h-3 w-3" /> Clear Chat
            </button>
          )}
        </div>
      )}

      {/* Chat Messages */}
      {hasHistory && (
        <div 
          ref={scrollRef}
          className="flex-1 p-4 overflow-y-auto max-h-[500px] space-y-6 bg-white scroll-smooth"
        >
          {messages.map((msg) => (
            <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className="h-8 w-8 rounded-full bg-primary-50 flex items-center justify-center shrink-0 border border-primary-100">
                  <Bot className="h-4 w-4 text-primary-600" />
                </div>
              )}
              
              <div className={`max-w-[85%] space-y-2`}>
                <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === 'user' 
                    ? 'bg-primary-600 text-white rounded-tr-none shadow-md shadow-primary-100 font-medium' 
                    : msg.error 
                      ? 'bg-red-50 text-red-700 border border-red-100 rounded-tl-none'
                      : 'bg-slate-50 text-slate-800 border border-slate-100 rounded-tl-none font-serif text-base'
                }`}>
                  {msg.content}
                </div>

                {msg.citations && msg.citations.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 px-1">
                    {msg.citations.map((cit, idx) => (
                      <div 
                        key={idx}
                        className="inline-flex items-center gap-1 bg-white border border-slate-200 px-2 py-0.5 rounded text-[9px] font-bold text-slate-500 shadow-xs"
                      >
                        DOC {cit.document_id}
                        {cit.page && <span className="opacity-40 font-normal">| P.{cit.page}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="h-8 w-8 rounded-full bg-slate-100 flex items-center justify-center shrink-0 border border-slate-200">
                  <UserIcon className="h-4 w-4 text-slate-500" />
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-3 animate-pulse">
              <div className="h-8 w-8 rounded-full bg-primary-50 flex items-center justify-center border border-primary-100">
                <Bot className="h-4 w-4 text-primary-300" />
              </div>
              <div className="bg-slate-50 border border-slate-100 rounded-2xl rounded-tl-none px-4 py-3 flex items-center gap-2">
                <Loader2 className="h-3 w-3 animate-spin text-primary-400" />
                <span className="text-xs font-medium text-slate-400 italic">Legal Analyst is thinking...</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Input Area */}
      <div className={`p-2 shrink-0 ${hasHistory ? 'border-t border-slate-50 bg-slate-50/30' : ''}`}>
        <form onSubmit={handleAsk} className="relative flex items-end gap-2">
          {!isFocused && !question && !hasHistory && (
            <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none flex items-center gap-2 text-slate-400">
              <Sparkles className="h-4 w-4 text-primary-400" />
              <span className="text-sm font-medium">Ask a legal question about this case...</span>
            </div>
          )}
          
          <textarea
            value={question}
            onFocus={() => setIsFocused(true)}
            onBlur={() => !question && !hasHistory && setIsFocused(false)}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleAsk(e);
              }
            }}
            placeholder=""
            rows={isFocused || hasHistory ? 2 : 1}
            className={`w-full pl-4 pr-12 py-3 bg-slate-50/50 border-none rounded-xl focus:bg-white focus:ring-0 outline-none resize-none transition-all text-sm font-medium ${isFocused || hasHistory ? 'min-h-[60px]' : 'min-h-[48px]'}`}
            disabled={isLoading}
          />
          
          <button
            type="submit"
            disabled={isLoading || !question.trim()}
            className={`absolute right-2 bottom-2 p-2 rounded-lg transition-all shadow-sm ${question.trim() ? 'bg-primary-600 text-white hover:bg-primary-700' : 'bg-slate-100 text-slate-300'}`}
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </form>
      </div>
    </div>
  );
};

export default AskAI;

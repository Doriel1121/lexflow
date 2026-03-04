import { useState, FormEvent } from 'react';
import { Search, Loader2, FileText, Tag, Link } from 'lucide-react';
import api from '../services/api';
import { Document } from '../types';

const SearchPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<'full-text' | 'semantic'>('full-text');
  const [results, setResults] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResults([]);

    try {
      let response;
      if (searchType === 'full-text') {
        response = await api.get(`/v1/search?query_string=${query}`);
      } else {
        response = await api.get(`/v1/search?semantic_query=${query}`);
      }
      setResults(response.data);
    } catch (err) {
      console.error('Search failed:', err);
      setError('Failed to perform search. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col p-6 animate-in fade-in duration-300">
      <div className="mb-6">
        <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">Search Hub</h1>
        <p className="text-slate-500 mt-1">Cross-examine your entire document database using keywords or AI context.</p>
      </div>
      
      <div className="bg-card border border-border rounded-xl shadow-sm p-6 mb-6 shrink-0">
        <form onSubmit={handleSearch} className="space-y-6">
          
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input
              type="text"
              id="searchQuery"
              className="w-full pl-12 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-md focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-slate-800 placeholder-slate-400"
              placeholder="Search clauses, dates, subjects, or ask a question..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center space-x-6">
              <span className="text-sm font-semibold text-slate-700">Search Engine:</span>
              <label className="flex items-center space-x-2 cursor-pointer group">
                <div className="relative flex items-center justify-center">
                  <input
                    type="radio"
                    name="searchType"
                    value="full-text"
                    checked={searchType === 'full-text'}
                    onChange={() => setSearchType('full-text')}
                    className="peer sr-only"
                  />
                  <div className="w-4 h-4 rounded-full border-2 border-slate-300 peer-checked:border-primary peer-checked:bg-primary transition-all"></div>
                </div>
                <span className="text-sm font-medium text-slate-600 group-hover:text-slate-900 transition-colors">Exact Match</span>
              </label>
              
              <label className="flex items-center space-x-2 cursor-pointer group">
                <div className="relative flex items-center justify-center">
                  <input
                    type="radio"
                    name="searchType"
                    value="semantic"
                    checked={searchType === 'semantic'}
                    onChange={() => setSearchType('semantic')}
                    className="peer sr-only"
                  />
                  <div className="w-4 h-4 rounded-full border-2 border-slate-300 peer-checked:border-primary peer-checked:bg-primary transition-all"></div>
                </div>
                <span className="text-sm font-medium text-slate-600 group-hover:text-slate-900 transition-colors">Semantic Intelligence</span>
              </label>
            </div>
            
            <button
              type="submit"
              className="px-6 py-2.5 bg-primary text-primary-foreground font-medium rounded-xl hover:bg-primary/90 transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              disabled={loading || !query}
            >
              {loading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Querying...</>
              ) : (
                <><Search className="h-4 w-4" /> Run Search</>
              )}
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-100 rounded-xl flex items-center gap-3 text-red-600 text-sm mb-6 shrink-0">
          <span>{error}</span>
        </div>
      )}

      {results.length > 0 && (
        <div className="flex-1 overflow-y-auto">
          <h2 className="text-lg font-bold text-slate-800 mb-4 px-1">{results.length} Matches Found</h2>
          <div className="grid grid-cols-1 gap-4 pb-6">
            {results.map((doc) => (
              <div key={doc.id} className="bg-white border border-slate-200 rounded-xl p-5 hover:border-primary/50 hover:shadow-md transition-all group">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-primary/10 rounded-lg shrink-0 mt-1 cursor-pointer">
                      <FileText className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-slate-800 leading-tight group-hover:text-primary transition-colors cursor-pointer">{doc.filename}</h3>
                      <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                        <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                          Case #{doc.case_id}
                        </span>
                        <span className="flex items-center text-xs text-slate-500">
                          <Tag className="h-3 w-3 mr-1" />
                          {doc.classification || 'Unclassified'}
                        </span>
                      </div>
                      
                      {doc.content && (
                        <p className="text-sm text-slate-600 mt-3 line-clamp-2 leading-relaxed font-serif">
                          "...{doc.content}..."
                        </p>
                      )}
                    </div>
                  </div>
                  
                  <a 
                    href={doc.s3_url} 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="flex items-center justify-center p-2 bg-slate-50 text-slate-600 hover:text-primary hover:bg-primary/10 rounded-lg transition-colors border border-slate-200"
                    title="Download Source File"
                  >
                    <Link className="h-4 w-4" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {results.length === 0 && !loading && !error && query && (
        <div className="flex-1 flex flex-col items-center justify-center py-12 text-center text-slate-500">
          <div className="p-4 bg-slate-100/50 rounded-full mb-4 ring-8 ring-slate-50">
            <Search className="h-8 w-8 text-slate-400" />
          </div>
          <p className="text-lg font-semibold text-slate-700">No matches found</p>
          <p className="text-sm mt-1 max-w-sm leading-relaxed">We couldn't find any documents matching "{query}" across the database.</p>
        </div>
      )}
    </div>
  );
};

export default SearchPage;

import { useState, useEffect } from 'react';
import api from '../../services/api';
import { Tag } from '../../types';
import { FolderGit2, Hash, Building2, Search, ArrowRight, Loader2, Scale, FileText, Tag as TagIcon, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';

// Predefined collection categories (order determines tab order)
const CATEGORIES = [
  { key: '',              label: 'All' },
  { key: 'client_id',    label: 'Client ID' },
  { key: 'project',      label: 'Project' },
  { key: 'organization', label: 'Organization' },
  { key: 'case_type',    label: 'Case Type' },
  { key: 'document_type',label: 'Document Type' },
];

export function CollectionsList() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState('');
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    fetchTags(activeCategory);
  }, [activeCategory]);

  const fetchTags = async (category: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: '200' });
      if (category) params.append('category', category);
      const response = await api.get(`/v1/tags?${params.toString()}`);
      setTags(response.data);
    } catch (error) {
      console.error('Failed to fetch collections:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncCollections = async () => {
    setSyncing(true);
    try {
      await api.post('/v1/documents/assign-collections-bulk');
      // Wait a bit for the background task to make progress
      setTimeout(() => fetchTags(activeCategory), 2000);
    } catch (error) {
      console.error('Failed to sync collections:', error);
    } finally {
      setSyncing(false);
    }
  };

  const filteredTags = tags.filter(t =>
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    (t.category && t.category.toLowerCase().includes(search.toLowerCase()))
  );

  const getCategoryIcon = (category?: string) => {
    switch (category) {
      case 'client_id':    return <Hash className="h-5 w-5 text-emerald-500" />;
      case 'project':      return <FolderGit2 className="h-5 w-5 text-indigo-500" />;
      case 'organization': return <Building2 className="h-5 w-5 text-blue-500" />;
      case 'case_type':    return <Scale className="h-5 w-5 text-purple-500" />;
      case 'document_type':return <FileText className="h-5 w-5 text-orange-500" />;
      default:             return <TagIcon className="h-5 w-5 text-slate-400" />;
    }
  };

  const getCategoryTheme = (category?: string) => {
    switch (category) {
      case 'client_id':    return 'bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20';
      case 'project':      return 'bg-indigo-50 text-indigo-700 border-indigo-100 dark:bg-indigo-500/10 dark:text-indigo-400 dark:border-indigo-500/20';
      case 'organization': return 'bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/20';
      case 'case_type':    return 'bg-purple-50 text-purple-700 border-purple-100 dark:bg-purple-500/10 dark:text-purple-400 dark:border-purple-500/20';
      case 'document_type':return 'bg-orange-50 text-orange-700 border-orange-100 dark:bg-orange-500/10 dark:text-orange-400 dark:border-orange-500/20';
      default:             return 'bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700';
    }
  };

  const formatCategoryName = (cat?: string) => {
    if (!cat) return 'General';
    return cat.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Smart Collections</h1>
          <p className="text-muted-foreground mt-1">
            Documents automatically organized by AI-extracted entities.
          </p>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto mt-4 md:mt-0">
          <button
            onClick={handleSyncCollections}
            disabled={syncing}
            className="flex items-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground hover:bg-secondary/80 rounded-lg text-sm font-medium transition-colors whitespace-nowrap"
          >
            {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {syncing ? 'Syncing...' : 'Sync Missing Docs'}
          </button>
          
          <div className="relative flex-1 md:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search collections..."
              className="w-full pl-9 pr-4 py-2 bg-background border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Category Filter Tabs */}
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Filter by category">
        {CATEGORIES.map(cat => (
          <button
            key={cat.key}
            id={`tab-${cat.key || 'all'}`}
            role="tab"
            aria-selected={activeCategory === cat.key}
            onClick={() => setActiveCategory(cat.key)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-all duration-150 ${
              activeCategory === cat.key
                ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                : 'bg-background text-muted-foreground border-border hover:border-primary/40 hover:text-foreground'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-primary/50" />
        </div>
      ) : filteredTags.length === 0 ? (
        <div className="text-center py-16 bg-card rounded-xl border border-dashed">
          <FolderGit2 className="h-12 w-12 text-muted-foreground/50 mx-auto mb-4" />
          <h3 className="text-lg font-medium">No collections found</h3>
          <p className="text-muted-foreground mt-1 max-w-sm mx-auto">
            Upload documents and our AI will automatically organize them into projects and entities.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTags.map((tag) => (
            <Link
              key={tag.id}
              to={`/collections/${tag.id}`}
              className="group relative flex flex-col p-5 bg-card border rounded-xl hover:shadow-md transition-all duration-200 hover:border-primary/20"
            >
              <div className="flex items-start justify-between mb-4">
                <div className={`p-2 rounded-lg border ${getCategoryTheme(tag.category)}`}>
                  {getCategoryIcon(tag.category)}
                </div>
                <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${getCategoryTheme(tag.category)}`}>
                  {formatCategoryName(tag.category)}
                </span>
              </div>

              <h3 className="text-lg font-medium line-clamp-1 mb-1 group-hover:text-primary transition-colors">
                {tag.name}
              </h3>

              <div className="mt-auto pt-4 flex items-center justify-between text-sm text-muted-foreground border-t border-border/50">
                <span className="flex items-center gap-1">
                  <FileText className="h-3.5 w-3.5" />
                  {(tag as any).document_count ?? 0} document{((tag as any).document_count ?? 0) !== 1 ? 's' : ''}
                </span>
                <span className="flex items-center gap-1 group-hover:text-primary transition-colors">
                  View
                  <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

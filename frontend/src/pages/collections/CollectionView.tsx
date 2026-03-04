import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../../services/api';
import { Tag, Document } from '../../types';
import { FolderGit2, Hash, Building2, ChevronLeft, Calendar, FileText, Scale, Tag as TagIcon } from 'lucide-react';
import { format } from 'date-fns';

export function CollectionView() {
  const { id } = useParams<{ id: string }>();
  const [tag, setTag] = useState<Tag | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCollection();
  }, [id]);

  const fetchCollection = async () => {
    try {
      // Fetch the specific Tag first
      const tagResponse = await api.get(`/v1/tags/${id}`);
      setTag(tagResponse.data);

      // Fetch documents assigned to this tag
      const docResponse = await api.get(`/v1/documents?tag=${id}`);
      setDocuments(docResponse.data);
    } catch (error) {
      console.error('Failed to fetch collection details:', error);
    } finally {
      setLoading(false);
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

  const getCategoryIcon = (category?: string) => {
    switch (category) {
      case 'client_id':    return <Hash className="h-4 w-4 mr-2" />;
      case 'project':      return <FolderGit2 className="h-4 w-4 mr-2" />;
      case 'organization': return <Building2 className="h-4 w-4 mr-2" />;
      case 'case_type':    return <Scale className="h-4 w-4 mr-2" />;
      case 'document_type':return <FileText className="h-4 w-4 mr-2" />;
      default:             return <TagIcon className="h-4 w-4 mr-2" />;
    }
  };

  if (loading) return <div className="p-8 text-center text-muted-foreground animate-pulse">Loading collection...</div>;
  if (!tag) return <div className="p-8 text-center text-red-500 bg-red-50 rounded-lg">Collection not found</div>;

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <Link to="/collections" className="inline-flex items-center text-sm font-medium text-muted-foreground hover:text-primary transition-colors">
          <ChevronLeft className="h-4 w-4 mr-1" />
          Back to Smart Collections
        </Link>
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-3">
             <div className={`p-2.5 rounded-lg border ${getCategoryTheme(tag.category)}`}>
               {getCategoryIcon(tag.category)}
             </div>
            <h1 className="text-2xl font-semibold tracking-tight">{tag.name}</h1>
          </div>
          <span className={`text-xs font-semibold px-3 py-1 rounded-full border flex items-center ${getCategoryTheme(tag.category)}`}>
            {getCategoryIcon(tag.category)}
            {tag.category ? tag.category.charAt(0).toUpperCase() + tag.category.slice(1).replace('_', ' ') : 'General'}
          </span>
        </div>
        <p className="text-muted-foreground">
          Showing all documents the AI automatically categorized under this collection.
        </p>
      </div>

      {/* Document Grid */}
      {documents.length === 0 ? (
        <div className="text-center py-16 bg-card rounded-xl border border-dashed text-muted-foreground">
          <FileText className="h-10 w-10 mx-auto mb-3 opacity-50" />
          No documents have been categorized under this collection yet.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {documents.map(doc => (
            <Link 
              key={doc.id}
              to={`/documents/${doc.id}`}
              className="flex flex-col p-4 bg-card border rounded-xl hover:shadow-md hover:border-primary/40 transition-all duration-200"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-primary/10 rounded-lg shrink-0">
                  <FileText className="h-5 w-5 text-primary" />
                </div>
                <h3 className="font-medium text-sm line-clamp-2" title={doc.filename}>
                  {doc.filename}
                </h3>
              </div>
              <div className="mt-auto flex items-center justify-between text-xs text-muted-foreground pt-3 border-t border-border/50">
                <span className="flex items-center">
                  <Calendar className="h-3.5 w-3.5 mr-1" />
                  {format(new Date(doc.created_at), 'MMM d, yyyy')}
                </span>
                <span className="bg-muted px-2 py-0.5 rounded-md text-foreground">
                  View Source
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

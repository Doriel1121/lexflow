import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Search,
  Loader2,
  FileText,
  Tag,
  Link,
  Briefcase,
  Users,
  ChevronRight,
  AlertCircle,
  FileSearch,
} from "lucide-react";
import api from "../services/api";
import { GlobalSearchResult } from "../types";

const SearchPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const urlQuery = searchParams.get("q") || "";

  const [query, setQuery] = useState(urlQuery);
  const [results, setResults] = useState<GlobalSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const performSearch = useCallback(async (searchTerm: string) => {
    if (!searchTerm || searchTerm.length < 2) return;

    setLoading(true);
    setError(null);
    try {
      const response = await api.get<GlobalSearchResult>(
        `/v1/search?query=${encodeURIComponent(searchTerm)}`,
      );
      setResults(response.data);
    } catch (err) {
      console.error("Search failed:", err);
      setError(t("searchPage.searchFailed"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (urlQuery) {
      setQuery(urlQuery);
      performSearch(urlQuery);
    }
  }, [urlQuery, performSearch]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  };

  const hasResults =
    results &&
    (results.cases.length > 0 ||
      results.documents.length > 0 ||
      results.clients.length > 0);

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-500">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-slate-800 tracking-tight flex items-center gap-2">
          <FileSearch className="h-6 w-6 text-primary" />
          {t("searchPage.title")}
        </h1>
        <p className="text-slate-500 text-sm">{t("searchPage.subtitle")}</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input
              type="text"
              className="w-full pl-12 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
              placeholder={t("searchPage.searchPlaceholder")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
          </div>
          <button
            type="submit"
            disabled={loading || query.length < 2}
            className="px-6 py-3 bg-slate-900 text-white rounded-xl font-medium hover:bg-slate-800 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            {t("searchPage.search")}
          </button>
        </form>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 text-red-600 p-4 rounded-xl flex items-center gap-3">
          <AlertCircle className="h-5 w-5" />
          {error}
        </div>
      )}

      {loading && !results && (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
          <p className="text-slate-500 font-medium">
            {t("searchPage.scanning")}
          </p>
        </div>
      )}

      {results && (
        <div className="grid grid-cols-1 gap-8 pb-10">
          {/* CLIENTS SECTION */}
          {results.clients.length > 0 && (
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  {t("searchPage.clients")} ({results.clients.length})
                </h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {results.clients.map((client) => (
                  <div
                    key={client.id}
                    onClick={() => navigate(`/clients/${client.id}`)}
                    className="bg-white border border-slate-200 rounded-xl p-4 hover:border-primary/40 hover:shadow-md transition-all cursor-pointer group"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center font-bold">
                          {client.name.charAt(0)}
                        </div>
                        <div>
                          \n{" "}
                          <h3 className="font-bold text-slate-800 group-hover:text-primary transition-colors">
                            {client.name}
                          </h3>
                          <p className="text-xs text-slate-500 truncate max-w-[150px]">
                            {client.contact_email || t("searchPage.noEmail")}
                          </p>
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-primary transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* CASES SECTION */}
          {results.cases.length > 0 && (
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                  <Briefcase className="h-4 w-4" />
                  {t("searchPage.cases")} ({results.cases.length})
                </h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {results.cases.map((caseItem) => (
                  <div
                    key={caseItem.id}
                    onClick={() => navigate(`/cases/${caseItem.id}`)}
                    className="bg-white border border-slate-200 rounded-xl p-4 hover:border-primary/40 hover:shadow-md transition-all cursor-pointer group flex items-center justify-between"
                  >
                    <div className="flex items-center gap-4">
                      <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-lg">
                        <Briefcase className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="font-bold text-slate-800 group-hover:text-primary transition-colors">
                          {caseItem.title}
                        </h3>
                        <div className="flex items-center gap-2 mt-1">
                          <span
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                              caseItem.status?.toLowerCase() === "open"
                                ? "bg-green-100 text-green-700"
                                : "bg-slate-100 text-slate-600"
                            }`}
                          >
                            {caseItem.status}
                          </span>
                          <span className="text-xs text-slate-400">
                            {t("searchPage.created")}{" "}
                            {new Date(caseItem.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    </div>
                    <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-primary transition-colors" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* DOCUMENTS SECTION */}
          {results.documents.length > 0 && (
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  {t("searchPage.documents")} ({results.documents.length})
                </h2>
              </div>
              <div className="grid grid-cols-1 gap-3">
                {results.documents.map((doc) => (
                  <div
                    key={doc.id}
                    onClick={() => navigate(`/documents/${doc.id}`)}
                    className="bg-white border border-slate-200 rounded-xl p-4 hover:border-primary/40 hover:shadow-sm transition-all cursor-pointer group flex items-center justify-between"
                  >
                    <div className="flex items-center gap-4">
                      <div className="p-2 bg-slate-50 text-slate-400 group-hover:bg-primary/10 group-hover:text-primary transition-colors rounded-lg">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="font-bold text-slate-800 group-hover:text-primary transition-colors">
                          {doc.filename}
                        </h3>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded flex items-center gap-1">
                            <Tag className="h-3 w-3" />
                            {doc.classification || t("searchPage.unclassified")}
                          </span>
                          {doc.case_id && (
                            <span className="text-xs text-slate-400">
                              {t("searchPage.caseNumber")} {doc.case_id}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <a
                        href={doc.s3_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="p-2 text-slate-400 hover:text-primary hover:bg-slate-50 rounded-lg transition-all"
                      >
                        <Link className="h-4 w-4" />
                      </a>
                      <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-primary transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!hasResults && !loading && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="bg-slate-50 p-6 rounded-full mb-4">
                <Search className="h-10 w-10 text-slate-300" />
              </div>
              <h3 className="text-lg font-bold text-slate-800">
                {t("searchPage.noMatches")}
              </h3>
              <p className="text-slate-500 text-sm max-w-xs mt-1">
                {t("searchPage.noMatchesDesc", { query })}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SearchPage;

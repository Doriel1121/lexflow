import { useState, useEffect } from "react";
import {
  useFloating,
  autoUpdate,
  offset,
  flip,
  shift,
  useClick,
  useDismiss,
  useRole,
  useInteractions,
} from "@floating-ui/react";
import { useTranslation } from "react-i18next";
import api from "../../services/api";
import { Tag } from "../../types";
import { useSnackbar } from "../../context/SnackbarContext";
import {
  FolderGit2,
  Hash,
  Building2,
  Search,
  Loader2,
  Scale,
  FileText,
  Tag as TagIcon,
  RefreshCw,
  MoreVertical,
  ChevronDown,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

// Predefined collection categories (order determines tab order)
const CATEGORIES = [
  { key: "", label: "All" },
  { key: "client_id", label: "Client ID" },
  { key: "project", label: "Project" },
  { key: "organization", label: "Organization" },
  { key: "case_type", label: "Case Type" },
  { key: "document_type", label: "Document Type" },
];

export function CollectionsList() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [openDropdownId, setOpenDropdownId] = useState<number | null>(null);
  const [dropdownButtonElement, setDropdownButtonElement] =
    useState<HTMLElement | null>(null);

  // Set up Floating UI for smart dropdown positioning
  const { refs, floatingStyles, context } = useFloating({
    open: openDropdownId !== null,
    onOpenChange: (open) => {
      if (!open) setOpenDropdownId(null);
    },
    elements: {
      reference: dropdownButtonElement,
    },
    middleware: [
      offset(8), // 8px gap between button and menu
      flip({ padding: 8 }), // Flip to opposite side if goes off-screen
      shift({ padding: 8 }), // Shift to stay within viewport
    ],
    whileElementsMounted: autoUpdate, // Auto-update on scroll/resize
  });

  const click = useClick(context);
  const dismiss = useDismiss(context);
  const role = useRole(context);
  const { getFloatingProps } = useInteractions([click, dismiss, role]);

  useEffect(() => {
    fetchTags(activeCategory);
  }, [activeCategory]);

  useEffect(() => {
    const handleClickOutside = () => setOpenDropdownId(null);
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  const fetchTags = async (category: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (category) params.append("category", category);
      const response = await api.get(`/v1/tags?${params.toString()}`);
      setTags(response.data);
    } catch (error) {
      console.error("Failed to fetch collections:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncCollections = async () => {
    setSyncing(true);
    try {
      await api.post("/v1/documents/assign-collections-bulk");
      // Wait a bit for the background task to make progress
      setTimeout(() => fetchTags(activeCategory), 2000);
    } catch (error) {
      console.error("Failed to sync collections:", error);
    } finally {
      setSyncing(false);
    }
  };

  const filteredTags = tags.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      (t.category && t.category.toLowerCase().includes(search.toLowerCase())),
  );

  const getCategoryIcon = (category?: string) => {
    switch (category) {
      case "client_id":
        return <Hash className="h-5 w-5 text-emerald-500" />;
      case "project":
        return <FolderGit2 className="h-5 w-5 text-indigo-500" />;
      case "organization":
        return <Building2 className="h-5 w-5 text-blue-500" />;
      case "case_type":
        return <Scale className="h-5 w-5 text-purple-500" />;
      case "document_type":
        return <FileText className="h-5 w-5 text-orange-500" />;
      default:
        return <TagIcon className="h-5 w-5 text-slate-400" />;
    }
  };

  const getCategoryTheme = (category?: string) => {
    switch (category) {
      case "client_id":
        return "bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20";
      case "project":
        return "bg-indigo-50 text-indigo-700 border-indigo-100 dark:bg-indigo-500/10 dark:text-indigo-400 dark:border-indigo-500/20";
      case "organization":
        return "bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/20";
      case "case_type":
        return "bg-purple-50 text-purple-700 border-purple-100 dark:bg-purple-500/10 dark:text-purple-400 dark:border-purple-500/20";
      case "document_type":
        return "bg-orange-50 text-orange-700 border-orange-100 dark:bg-orange-500/10 dark:text-orange-400 dark:border-orange-500/20";
      default:
        return "bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700";
    }
  };

  const formatCategoryName = (cat?: string) => {
    if (!cat) return "General";
    return cat
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">
          {t("collections.title")}
        </h1>
        <p className="text-slate-600 mt-1">{t("collections.subtitle")}</p>
      </div>

      {/* Table Container */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col flex-1 min-h-0">
        {/* Toolbar */}
        <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder={t("collections.searchPlaceholder")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full ps-10 pe-4 py-2 bg-white border border-slate-200 focus:border-primary focus:ring-2 focus:ring-primary/20 rounded-lg text-sm outline-none"
              />
            </div>
            <div className="relative">
              <select
                value={activeCategory}
                onChange={(e) => setActiveCategory(e.target.value)}
                className="appearance-none ps-4 pe-10 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 cursor-pointer outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat.key} value={cat.key}>
                    {cat.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
            </div>
          </div>
          <button
            onClick={handleSyncCollections}
            disabled={syncing}
            className="flex items-center gap-2 px-4 py-2 bg-white text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 text-sm font-medium transition-all"
          >
            {syncing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {syncing ? t("collections.syncing") : t("collections.sync")}
          </button>
        </div>

        {/* Table */}
        <div className="overflow-x-auto flex-1">
          {loading ? (
            <div className="flex items-center justify-center h-64 gap-3 text-slate-400">
              <Loader2 className="h-6 w-6 animate-spin" />
              <span>{t("collections.loading")}</span>
            </div>
          ) : filteredTags.length === 0 ? (
            <div className="p-12 text-center text-slate-500">
              <FolderGit2 className="h-16 w-16 text-slate-300 mx-auto mb-4" />
              <p className="font-medium text-lg">
                {t("collections.noCollections")}
              </p>
              <p className="text-sm text-slate-400 mt-1">
                {t("collections.noCollectionsDesc")}
              </p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-2.5 text-left text-xs uppercase text-start tracking-wider w-12"></th>
                  <th className="px-2 py-2.5 text-left text-xs uppercase text-start tracking-wider">
                    {t("collections.collectionName")}
                  </th>
                  <th className="px-2 py-2.5 text-left text-xs uppercase text-start tracking-wider w-40">
                    {t("collections.category")}
                  </th>
                  <th className="px-2 py-2.5 text-center text-xs uppercase text-start tracking-wider w-28">
                    {t("collections.documents")}
                  </th>
                  <th className="px-2 py-2.5 text-right text-xs uppercase text-start tracking-wider w-12"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {filteredTags.map((tag) => (
                  <tr
                    key={tag.id}
                    className="hover:bg-slate-50 cursor-pointer transition-colors group"
                    onClick={() => navigate(`/collections/${tag.id}`)}
                  >
                    <td className="px-4 py-2.5">
                      <div className="p-1.5 rounded inline-flex">
                        {getCategoryIcon(tag.category)}
                      </div>
                    </td>
                    <td className="px-2 py-2.5">
                      <div className="flex flex-col">
                        <span className="font-medium text-slate-900 text-sm truncate">
                          {tag.name}
                        </span>
                        <span className="text-xs text-slate-500">
                          ID: {tag.id}
                        </span>
                      </div>
                    </td>
                    <td className="px-2 py-2.5">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-xs font-medium border ${getCategoryTheme(tag.category)}`}
                      >
                        {formatCategoryName(tag.category)}
                      </span>
                    </td>
                    <td className="px-2 py-2.5 text-center text-sm text-slate-700">
                      {(tag as any).document_count ?? 0}
                    </td>
                    <td className="px-2 py-2.5 text-right relative">
                      <button
                        className="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600 opacity-0 group-hover:opacity-100 transition-all"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDropdownButtonElement(
                            openDropdownId === tag.id
                              ? null
                              : (e.currentTarget as HTMLElement),
                          );
                          setOpenDropdownId(
                            openDropdownId === tag.id ? null : tag.id,
                          );
                        }}
                      >
                        <MoreVertical className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Dropdown Menu - Rendered at root level to avoid clipping */}
        {openDropdownId !== null && (
          <div
            ref={refs.setFloating}
            style={floatingStyles}
            className="w-44 bg-white border border-slate-200 rounded-lg shadow-lg z-50"
            {...getFloatingProps({
              onClick: (e) => e.stopPropagation(),
            })}
          >
            <div className="py-1">
              <button
                className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                onClick={() => {
                  navigate(`/collections/${openDropdownId}`);
                  setOpenDropdownId(null);
                }}
              >
                {t("collections.viewCollection")}
              </button>
              <button
                className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                onClick={() => {
                  setOpenDropdownId(null);
                  showSnackbar("Edit coming soon", { type: "info" });
                }}
              >
                {t("collections.editCollection")}
              </button>
              <hr className="my-1 border-slate-100" />
              <button
                className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                onClick={() => {
                  setOpenDropdownId(null);
                  if (window.confirm(t("collections.deleteConfirm")))
                    showSnackbar("Delete coming soon", { type: "info" });
                }}
              >
                {t("collections.deleteCollection")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

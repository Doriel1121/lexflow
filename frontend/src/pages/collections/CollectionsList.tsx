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
import { useConfirm } from "../../context/ConfirmContext";
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
  X,
  Lock,
  User,
  Sparkles,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

const CATEGORIES = [
  { key: "", label: "All" },
  { key: "client_id", label: "Client ID" },
  { key: "person", label: "Person" },
  { key: "project", label: "Project" },
  { key: "organization", label: "Organization" },
  { key: "case_type", label: "Case Type" },
  { key: "document_type", label: "Document Type" },
  { key: "ai_tag", label: "AI Tag" },
];

// Global const categories — system-managed, not user-editable
const SYSTEM_CATEGORIES = new Set(["case_type", "document_type"]);

export function CollectionsList() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const { confirm } = useConfirm();

  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [openDropdownId, setOpenDropdownId] = useState<number | null>(null);
  const [dropdownButtonElement, setDropdownButtonElement] =
    useState<HTMLElement | null>(null);

  // Edit modal state
  const [editingTag, setEditingTag] = useState<Tag | null>(null);
  const [editName, setEditName] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const { refs, floatingStyles, context } = useFloating({
    open: openDropdownId !== null,
    onOpenChange: (open) => { if (!open) setOpenDropdownId(null); },
    elements: { reference: dropdownButtonElement },
    middleware: [offset(8), flip({ padding: 8 }), shift({ padding: 8 })],
    whileElementsMounted: autoUpdate,
  });

  const click = useClick(context);
  const dismiss = useDismiss(context);
  const role = useRole(context);
  const { getFloatingProps } = useInteractions([click, dismiss, role]);

  useEffect(() => { fetchTags(activeCategory); }, [activeCategory]);

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
      const res = await api.post("/v1/documents/assign-collections-bulk");
      showSnackbar(
        t("collections.syncSuccess", {
          synced: res.data?.synced ?? 0,
          defaultValue: `Synced ${res.data?.synced ?? 0} document(s)`,
        }),
        { type: "success" },
      );
      setTimeout(() => fetchTags(activeCategory), 2000);
    } catch (error: any) {
      console.error("Failed to sync collections:", error);
      showSnackbar(
        error.response?.data?.detail || t("collections.syncFailed"),
        { type: "error" },
      );
    } finally {
      setSyncing(false);
    }
  };

  const isSystemTag = (tag: Tag) =>
    tag.organization_id === null || tag.organization_id === undefined
      ? SYSTEM_CATEGORIES.has(tag.category ?? "")
      : false;

  // ── Delete ────────────────────────────────────────────────────────────

  const handleDelete = async (tag: Tag) => {
    setOpenDropdownId(null);

    if (isSystemTag(tag)) {
      showSnackbar(t("collections.systemCollection"), { type: "warning" });
      return;
    }

    const count = tag.document_count ?? 0;
    const message = count > 0
      ? t("collections.deleteWarning", { count })
      : t("collections.deleteConfirm");

    const ok = await confirm(message, {
      variant: "danger",
      confirmLabel: t("common.delete"),
    });
    if (!ok) return;

    // Optimistic removal
    const previous = tags;
    setTags((prev) => prev.filter((t) => t.id !== tag.id));

    try {
      await api.delete(`/v1/tags/${tag.id}`);
      showSnackbar(t("collections.deleteSuccess"), { type: "success" });
    } catch (error: any) {
      setTags(previous);
      const status = error.response?.status;
      if (status === 403) {
        showSnackbar(t("collections.systemCollection"), { type: "warning" });
      } else {
        showSnackbar(
          error.response?.data?.detail ?? t("common.error"),
          { type: "error" }
        );
      }
    }
  };

  // ── Edit / Rename ─────────────────────────────────────────────────────

  const openEditModal = (tag: Tag) => {
    setOpenDropdownId(null);
    setEditingTag(tag);
    setEditName(tag.name);
    setEditError(null);
  };

  const handleEditSave = async () => {
    if (!editingTag || !editName.trim()) return;
    if (editName.trim() === editingTag.name) {
      setEditingTag(null);
      return;
    }

    setEditSaving(true);
    setEditError(null);

    try {
      const response = await api.patch(`/v1/tags/${editingTag.id}`, {
        name: editName.trim(),
      });
      setTags((prev) =>
        prev.map((t) => (t.id === editingTag.id ? { ...t, name: response.data.name } : t))
      );
      showSnackbar(t("collections.editSuccess"), { type: "success" });
      setEditingTag(null);
    } catch (error: any) {
      const status = error.response?.status;
      if (status === 409) {
        setEditError(t("collections.nameConflict"));
      } else if (status === 403) {
        setEditError(t("collections.systemCollection"));
      } else {
        setEditError(error.response?.data?.detail ?? t("common.error"));
      }
    } finally {
      setEditSaving(false);
    }
  };

  // ── Helpers ───────────────────────────────────────────────────────────

  const filteredTags = tags.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      (t.category && t.category.toLowerCase().includes(search.toLowerCase()))
  );

  const getCategoryIcon = (category?: string) => {
    switch (category) {
      case "client_id":    return <Hash className="h-5 w-5 text-emerald-500" />;
      case "person":       return <User className="h-5 w-5 text-teal-500" />;
      case "project":      return <FolderGit2 className="h-5 w-5 text-indigo-500" />;
      case "organization": return <Building2 className="h-5 w-5 text-blue-500" />;
      case "case_type":    return <Scale className="h-5 w-5 text-purple-500" />;
      case "document_type":return <FileText className="h-5 w-5 text-orange-500" />;
      case "ai_tag":       return <Sparkles className="h-5 w-5 text-amber-500" />;
      default:             return <TagIcon className="h-5 w-5 text-slate-400" />;
    }
  };

  const getCategoryTheme = (category?: string) => {
    switch (category) {
      case "client_id":    return "bg-emerald-50 text-emerald-700 border-emerald-100";
      case "person":       return "bg-teal-50 text-teal-700 border-teal-100";
      case "project":      return "bg-indigo-50 text-indigo-700 border-indigo-100";
      case "organization": return "bg-blue-50 text-blue-700 border-blue-100";
      case "case_type":    return "bg-purple-50 text-purple-700 border-purple-100";
      case "document_type":return "bg-orange-50 text-orange-700 border-orange-100";
      case "ai_tag":       return "bg-amber-50 text-amber-700 border-amber-100";
      default:             return "bg-slate-50 text-slate-700 border-slate-200";
    }
  };

  const formatCategoryName = (cat?: string) => {
    if (!cat) return "General";
    return cat.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
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
                  <option key={cat.key} value={cat.key}>{cat.label}</option>
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
            {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
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
              <p className="font-medium text-lg">{t("collections.noCollections")}</p>
              <p className="text-sm text-slate-400 mt-1">{t("collections.noCollectionsDesc")}</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-2.5 text-left text-xs uppercase tracking-wider w-12"></th>
                  <th className="px-2 py-2.5 text-left text-xs uppercase tracking-wider">
                    {t("collections.collectionName")}
                  </th>
                  <th className="px-2 py-2.5 text-left text-xs uppercase tracking-wider w-40">
                    {t("collections.category")}
                  </th>
                  <th className="px-2 py-2.5 text-center text-xs uppercase tracking-wider w-28">
                    {t("collections.documents")}
                  </th>
                  <th className="px-2 py-2.5 text-right text-xs uppercase tracking-wider w-12"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {filteredTags.map((tag) => {
                  const isSystem = isSystemTag(tag);
                  return (
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
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-slate-900 text-sm truncate">
                              {tag.name}
                            </span>
                            {isSystem && (
                              <div title={t("collections.systemCollection")}>
                                <Lock className="h-3 w-3 text-slate-300 shrink-0" />
                              </div>
                            )}
                          </div>
                          <span className="text-xs text-slate-500">ID: {tag.id}</span>
                        </div>
                      </td>
                      <td className="px-2 py-2.5">
                        <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium border ${getCategoryTheme(tag.category)}`}>
                          {formatCategoryName(tag.category)}
                        </span>
                      </td>
                      <td className="px-2 py-2.5 text-center text-sm text-slate-700">
                        {tag.document_count ?? 0}
                      </td>
                      <td className="px-2 py-2.5 text-right relative">
                        <button
                          className="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600 opacity-0 group-hover:opacity-100 transition-all"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDropdownButtonElement(
                              openDropdownId === tag.id ? null : (e.currentTarget as HTMLElement)
                            );
                            setOpenDropdownId(openDropdownId === tag.id ? null : tag.id);
                          }}
                        >
                          <MoreVertical className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Dropdown Menu */}
        {openDropdownId !== null && (() => {
          const tag = tags.find((t) => t.id === openDropdownId);
          if (!tag) return null;
          const isSystem = isSystemTag(tag);
          return (
            <div
              ref={refs.setFloating}
              style={floatingStyles}
              className="w-44 bg-white border border-slate-200 rounded-lg shadow-lg z-50"
              {...getFloatingProps({ onClick: (e) => e.stopPropagation() })}
            >
              <div className="py-1">
                <button
                  className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                  onClick={() => { navigate(`/collections/${openDropdownId}`); setOpenDropdownId(null); }}
                >
                  {t("collections.viewCollection")}
                </button>
                <button
                  className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 ${isSystem ? "text-slate-300 cursor-not-allowed" : "text-slate-700 hover:bg-slate-50"}`}
                  disabled={isSystem}
                  onClick={() => !isSystem && openEditModal(tag)}
                  title={isSystem ? t("collections.systemCollection") : undefined}
                >
                  {isSystem && <Lock className="h-3 w-3" />}
                  {t("collections.editCollection")}
                </button>
                <hr className="my-1 border-slate-100" />
                <button
                  className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 ${isSystem ? "text-slate-300 cursor-not-allowed" : "text-red-600 hover:bg-red-50"}`}
                  disabled={isSystem}
                  onClick={() => !isSystem && handleDelete(tag)}
                  title={isSystem ? t("collections.systemCollection") : undefined}
                >
                  {isSystem && <Lock className="h-3 w-3" />}
                  {t("collections.deleteCollection")}
                </button>
              </div>
            </div>
          );
        })()}
      </div>

      {/* Edit / Rename Modal */}
      {editingTag && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
          onClick={() => setEditingTag(null)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-5 border-b border-slate-100">
              <h3 className="font-bold text-slate-900">{t("collections.editModalTitle")}</h3>
              <button
                onClick={() => setEditingTag(null)}
                className="p-1.5 text-slate-400 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* Category — read-only */}
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                  {t("collections.category")}
                </label>
                <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium border ${getCategoryTheme(editingTag.category)}`}>
                  {formatCategoryName(editingTag.category)}
                </span>
              </div>

              {/* Name — editable */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  {t("collections.editNameLabel")}
                </label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => { setEditName(e.target.value); setEditError(null); }}
                  onKeyDown={(e) => e.key === "Enter" && handleEditSave()}
                  placeholder={t("collections.editNamePlaceholder")}
                  className={`w-full px-3 py-2.5 border rounded-xl text-sm outline-none transition-all ${
                    editError
                      ? "border-red-300 focus:ring-2 focus:ring-red-100"
                      : "border-slate-200 focus:ring-2 focus:ring-primary/20 focus:border-primary"
                  }`}
                  autoFocus
                />
                {editError && (
                  <p className="text-xs text-red-600 mt-1.5">{editError}</p>
                )}
              </div>
            </div>

            <div className="px-5 pb-5 flex gap-3">
              <button
                onClick={() => setEditingTag(null)}
                className="flex-1 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm font-semibold transition-colors"
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={handleEditSave}
                disabled={editSaving || !editName.trim()}
                className="flex-1 px-4 py-2.5 bg-primary hover:bg-primary/90 text-white rounded-xl text-sm font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {editSaving && <Loader2 className="h-4 w-4 animate-spin" />}
                {t("common.save")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

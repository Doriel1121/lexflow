import React, { useEffect, useState } from "react";
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
import { Link, useNavigate } from "react-router-dom";
import {
  Search,
  Filter,
  Plus,
  MoreVertical,
  Briefcase,
  ChevronDown,
} from "lucide-react";
import api from "../services/api";
import { Case } from "../types";
import { useSnackbar } from "../context/SnackbarContext";
import { useConfirm } from "../context/ConfirmContext";
import { useTranslation } from "react-i18next";

const CasesPage: React.FC = () => {
  const navigate = useNavigate();
  const { showSnackbar } = useSnackbar();
  const { confirm } = useConfirm();
  const { t } = useTranslation();
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
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

  // Infinite Scroll State
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [fetchingMore, setFetchingMore] = useState(false);
  const limit = 50;
  const observerTarget = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchCases(0);
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setOpenDropdownId(null);
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  const fetchCases = async (targetPage: number = 0) => {
    try {
      const skip = targetPage * limit;
      if (targetPage === 0) setLoading(true);
      else setFetchingMore(true);

      const response = await api.get("/v1/cases/", { params: { skip, limit } });
      const incomingCases = response.data;

      if (targetPage === 0) {
        setCases(incomingCases);
      } else {
        setCases((prev) => [...prev, ...incomingCases]);
      }

      setHasMore(incomingCases.length === limit);
      setPage(targetPage);
      setError(null);
    } catch (err: any) {
      console.error("Error fetching cases:", err);
      setError(
        err.response?.data?.detail || err.message || "Failed to fetch cases",
      );
    } finally {
      setLoading(false);
      setFetchingMore(false);
    }
  };

  // Intersection Observer for Infinite Scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading && !fetchingMore) {
          fetchCases(page + 1);
        }
      },
      { threshold: 1.0 },
    );

    if (observerTarget.current) {
      observer.observe(observerTarget.current);
    }

    return () => observer.disconnect();
  }, [hasMore, loading, fetchingMore, page]);

  const filteredCases = React.useMemo(() => {
    return cases.filter((caseItem) => {
      const matchesSearch =
        caseItem.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        caseItem.description
          ?.toLowerCase()
          .includes(searchTerm.toLowerCase()) ||
        caseItem.id.toString().includes(searchTerm);

      const matchesStatus =
        statusFilter === "all" || caseItem.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [cases, searchTerm, statusFilter]);

  const formatDate = (dateStr: string) => {
    if (!dateStr) return t("casesPage.notAvailable");
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      open: "bg-success-light text-success-dark border-success/20",
      pending: "bg-warning-light text-warning-dark border-warning/20",
      closed: "bg-neutral-100 text-neutral-600 border-neutral-200",
    };
    return styles[status as keyof typeof styles] || styles.pending;
  };

  if (loading && page === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <span className="animate-pulse text-neutral-500">
          {t("casesPage.loading")}
        </span>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-serif font-bold text-neutral-900 tracking-tight">
          {t("casesPage.title")}
        </h1>
        <p className="text-neutral-600 mt-1">{t("casesPage.subtitle")}</p>
      </div>

      {error && (
        <div className="mb-4 bg-error-light border border-error/20 text-error-dark px-4 py-3 rounded-lg">
          <strong>{t("common.error")}:</strong> {error}
        </div>
      )}

      {/* Table Container */}
      <div className="bg-white border border-border-light rounded-lg shadow-legal overflow-hidden flex flex-col flex-1">
        {/* Toolbar */}
        <div className="p-4 border-b border-border-light bg-background-secondary flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1">
            {/* Search */}
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
              <input
                type="text"
                placeholder={t("casesPage.searchPlaceholder")}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-white border border-border-light focus:border-primary-500 focus:ring-2 focus:ring-primary-100 rounded-lg text-sm outline-none transition-all"
              />
            </div>

            {/* Status Filter */}
            <div className="relative">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="appearance-none pl-4 pr-10 py-2.5 bg-white border border-border-light rounded-lg text-sm font-medium text-neutral-700 hover:bg-neutral-50 transition-all cursor-pointer outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100"
              >
                <option value="all">{t("casesPage.allStatus")}</option>
                <option value="open">{t("casesPage.open")}</option>
                <option value="pending">{t("casesPage.pending")}</option>
                <option value="closed">{t("casesPage.closed")}</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none" />
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 px-3 py-2.5 bg-white text-neutral-600 border border-border-light rounded-lg hover:bg-neutral-50 text-sm font-medium transition-all">
              <Filter className="h-4 w-4" />
              <span>{t("casesPage.moreFilters")}</span>
            </button>
            <Link
              to="/cases/new"
              className="flex items-center gap-2 px-4 py-2.5 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary-800 transition-all shadow-sm"
            >
              <Plus className="h-4 w-4" />
              <span>{t("casesPage.newCase")}</span>
            </Link>
          </div>
        </div>
        {/* Table */}
        <div className="overflow-x-auto flex-1">
          {filteredCases.length === 0 ? (
            <div className="p-12 text-center text-neutral-500">
              <div className="flex flex-col items-center gap-3">
                <Briefcase className="h-16 w-16 text-neutral-300" />
                <p className="font-medium text-lg">{t("casesPage.noCases")}</p>
                <p className="text-sm text-neutral-400">
                  {searchTerm || statusFilter !== "all"
                    ? t("casesPage.noCases")
                    : t("casesPage.createFirstCase")}
                </p>
                {!searchTerm && statusFilter === "all" && (
                  <Link
                    to="/cases/new"
                    className="mt-4 px-4 py-2 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary-800 transition-all"
                  >
                    {t("casesPage.createFirstCase")}
                  </Link>
                )}
              </div>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-neutral-50 text-neutral-700 font-semibold border-b border-border-light sticky top-0">
                <tr>
                  <th className="px-4 py-2.5 text-left text-xs uppercase text-start tracking-wider w-12"></th>
                  <th className="px-2 py-2.5 text-left text-xs uppercase text-start tracking-wider">
                    {t("casesPage.caseTitle")}
                  </th>
                  <th className="px-2 py-2.5 text-left text-xs uppercase text-start tracking-wider w-24">
                    {t("casesPage.status")}
                  </th>
                  <th className="px-2 py-2.5 text-left text-xs uppercase text-start tracking-wider w-32">
                    {t("casesPage.client")}
                  </th>
                  <th className="px-2 py-2.5 text-left text-xs uppercase text-start tracking-wider w-28">
                    {t("casesPage.date")}
                  </th>
                  <th className="px-2 py-2.5 text-center text-xs uppercase text-start tracking-wider w-20">
                    {t("casesPage.docs")}
                  </th>
                  <th className="px-2 py-2.5 text-center text-xs uppercase text-start tracking-wider w-20">
                    {t("casesPage.notes")}
                  </th>
                  <th className="px-2 py-2.5 text-right text-xs uppercase text-start tracking-wider w-12"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light bg-white">
                {filteredCases.map((caseItem) => (
                  <tr
                    key={caseItem.id}
                    className="hover:bg-neutral-50 cursor-pointer transition-colors group"
                    onClick={() => navigate(`/cases/${caseItem.id}`)}
                  >
                    <td className="px-4 py-2.5">
                      <div className="p-1.5 bg-primary-50 rounded text-primary-600 inline-flex">
                        <Briefcase className="h-3.5 w-3.5" />
                      </div>
                    </td>
                    <td className="px-2 py-2.5">
                      <div className="flex flex-col">
                        <span className="font-medium text-neutral-900 text-sm truncate">
                          {caseItem.title}
                        </span>
                        <span className="text-xs text-neutral-500">
                          #{caseItem.id}
                        </span>
                      </div>
                    </td>
                    <td className="px-2 py-2.5">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-xs font-medium border ${getStatusBadge(caseItem.status)}`}
                      >
                        {caseItem.status === "open"
                          ? t("casesPage.open")
                          : caseItem.status === "pending"
                            ? t("casesPage.pending")
                            : caseItem.status === "closed"
                              ? t("casesPage.closed")
                              : caseItem.status}
                      </span>
                    </td>
                    <td className="px-2 py-2.5 text-sm text-neutral-700">
                      {caseItem.client_id
                        ? `${t("casesPage.client")} #${caseItem.client_id}`
                        : t("casesPage.noClient")}
                    </td>
                    <td className="px-2 py-2.5 text-xs text-neutral-600">
                      {formatDate(caseItem.created_at)}
                    </td>
                    <td className="px-2 py-2.5 text-center text-sm text-neutral-600">
                      {caseItem.documents?.length || 0}
                    </td>
                    <td className="px-2 py-2.5 text-center text-sm text-neutral-600">
                      {caseItem.notes?.length || 0}
                    </td>
                    <td className="px-2 py-2.5 text-right relative">
                      <button
                        className="p-1 hover:bg-neutral-200 rounded text-neutral-400 hover:text-neutral-600 opacity-0 group-hover:opacity-100 transition-all"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDropdownButtonElement(
                            openDropdownId === caseItem.id
                              ? null
                              : (e.currentTarget as HTMLElement),
                          );
                          setOpenDropdownId(
                            openDropdownId === caseItem.id ? null : caseItem.id,
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
            className="w-44 bg-white border border-border-light rounded-lg shadow-legal-lg z-50"
            {...getFloatingProps({
              onClick: (e) => e.stopPropagation(),
            })}
          >
            <div className="py-1">
              <button
                className="w-full text-left px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-50"
                onClick={() => {
                  navigate(`/cases/${openDropdownId}`);
                  setOpenDropdownId(null);
                }}
              >
                {t("casesPage.viewDetails")}
              </button>
              <button
                className="w-full text-left px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-50"
                onClick={() => {
                  setOpenDropdownId(null);
                  showSnackbar(t("casesPage.editComingSoon"), {
                    type: "info",
                  });
                }}
              >
                {t("casesPage.editCase")}
              </button>
              <hr className="my-1 border-neutral-100" />
              <button
                className="w-full text-left px-3 py-2 text-sm text-error hover:bg-error-light"
                onClick={async () => {
                  setOpenDropdownId(null);
                  const ok = await confirm(t("casesPage.deleteConfirm"), {
                    variant: "danger",
                    confirmLabel: t("common.delete"),
                  });
                  if (ok) showSnackbar(t("casesPage.deleteComingSoon"), { type: "info" });
                }}
              >
                {t("casesPage.deleteCase")}
              </button>
            </div>
          </div>
        )}

        {/* Infinite Scroll Sentinel */}
        {!loading && filteredCases.length > 0 && (
          <div
            ref={observerTarget}
            className="py-4 text-center border-t border-border-light"
          >
            {fetchingMore && (
              <span className="text-sm text-neutral-500 animate-pulse">
                {t("casesPage.loading")}
              </span>
            )}
            {!hasMore && cases.length > 0 && (
              <span className="text-xs text-neutral-400">
                {t("adminAudit.endOfRecords")}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CasesPage;

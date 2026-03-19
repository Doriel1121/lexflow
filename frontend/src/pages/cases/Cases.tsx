import React, { useState, useEffect } from "react";
import {
  Plus,
  Briefcase,
  AlertCircle,
  Loader2,
  FolderOpen,
  X,
  Search,
  MoreVertical,
  ChevronDown,
  UserPlus,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import api from "../../services/api";
import { EntityVerification } from "../../components/cases/EntityVerification";
import { useSnackbar } from "../../context/SnackbarContext";

interface Case {
  id: number;
  title: string;
  description: string;
  status: string;
  client_id: number;
  created_at: string;
}

interface Client {
  id: number;
  name: string;
  email: string;
  phone?: string;
}

export default function Cases() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    client_id: null as number | null,
  });
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [openDropdownId, setOpenDropdownId] = useState<number | null>(null);
  const [showAssignClientModal, setShowAssignClientModal] = useState(false);
  const [selectedCaseForAssignment, setSelectedCaseForAssignment] = useState<
    number | null
  >(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    fetchCases();
    fetchClients();
  }, []);

  useEffect(() => {
    const handleClickOutside = () => setOpenDropdownId(null);
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

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

  const fetchCases = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get("/v1/cases/");
      setCases(response.data);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Failed to load cases. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  const fetchClients = async () => {
    try {
      const response = await api.get("/v1/clients/");
      setClients(response.data);
    } catch (err: any) {
      console.error("Failed to load clients:", err);
    }
  };

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.post("/v1/cases/", formData);
      setShowCreateModal(false);
      setFormData({ title: "", description: "", client_id: null });
      fetchCases();
    } catch (err: any) {
      showSnackbar(
        err.response?.data?.detail ||
          "Failed to create case. Please try again.",
        { type: "error" },
      );
    } finally {
      setCreating(false);
    }
  };

  const handleAssignClient = async () => {
    if (!selectedCaseForAssignment || !selectedClientId) return;

    setAssigning(true);
    try {
      const caseToUpdate = cases.find(
        (c) => c.id === selectedCaseForAssignment,
      );
      if (!caseToUpdate) return;

      await api.put(`/v1/cases/${selectedCaseForAssignment}`, {
        title: caseToUpdate.title,
        description: caseToUpdate.description,
        status: caseToUpdate.status,
        client_id: selectedClientId,
      });
      setShowAssignClientModal(false);
      setSelectedCaseForAssignment(null);
      setSelectedClientId(null);
      fetchCases();
    } catch (err: any) {
      showSnackbar(err.response?.data?.detail || "Failed to assign client", {
        type: "error",
      });
    } finally {
      setAssigning(false);
    }
  };

  const openAssignClientModal = (caseId: number) => {
    setSelectedCaseForAssignment(caseId);
    setShowAssignClientModal(true);
    setOpenDropdownId(null);
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "open":
        return "bg-green-100 text-green-700 border border-green-200";
      case "pending":
        return "bg-amber-100 text-amber-700 border border-amber-200";
      case "closed":
        return "bg-slate-100 text-slate-600 border border-slate-200";
      case "in_progress":
        return "bg-blue-100 text-blue-700 border border-blue-200";
      default:
        return "bg-slate-100 text-slate-600 border border-slate-200";
    }
  };

  const getTranslatedStatus = (status: string) => {
    switch (status.toLowerCase()) {
      case "open":
        return t("casesPage.open");
      case "pending":
        return t("status.pending");
      case "closed":
        return t("casesPage.closed");
      case "active":
        return t("status.active");
      default:
        return status.replace(/_/g, " ");
    }
  };

  const getClientName = (clientId: number) => {
    const client = clients.find((c) => c.id === clientId);
    return client ? client.name : `Client #${clientId}`;
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">
            {t("casesPage.title")}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t("casesPage.subtitle")}
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center space-x-2 bg-primary text-primary-foreground px-4 py-2.5 rounded-xl hover:bg-primary/90 transition-colors shadow-sm font-medium"
        >
          <Plus className="h-4 w-4" />
          <span>{t("casesPage.newCase")}</span>
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center h-64 gap-3 text-slate-400">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span>{t("common.loading")}</span>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-xl flex items-center gap-3 text-destructive text-sm max-w-md">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchCases}
            className="px-4 py-2 border border-slate-200 rounded-lg text-sm hover:bg-slate-50 transition-colors"
          >
            {t("casesPage.tryAgain")}
          </button>
        </div>
      ) : cases.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 gap-4 text-center">
          <div className="p-4 bg-slate-100 rounded-full">
            <FolderOpen className="h-8 w-8 text-slate-400" />
          </div>
          <div>
            <p className="font-semibold text-slate-700">
              {t("casesPage.noCasesYet")}
            </p>
            <p className="text-sm text-slate-500 mt-1">
              {t("casesPage.createFirstDesc")}
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            {t("casesPage.createFirstCase")}
          </button>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col flex-1 min-h-0">
          {/* Toolbar */}
          <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 flex-1">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  placeholder={t("casesPage.searchPlaceholder")}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-white border border-slate-200 focus:border-primary focus:ring-2 focus:ring-primary/20 rounded-lg text-sm outline-none"
                />
              </div>
              <div className="relative">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="appearance-none pl-4 pr-10 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 cursor-pointer outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                  <option value="all">{t("casesPage.allStatus")}</option>
                  <option value="open">{t("casesPage.open")}</option>
                  <option value="pending">{t("casesPage.pending")}</option>
                  <option value="closed">{t("casesPage.closed")}</option>
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
              </div>
            </div>
          </div>
          {/* Table */}
          <div className="flex-1 overflow-auto">
            {filteredCases.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <p>{t("casesPage.noCases")}</p>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
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
                    <th className="px-2 py-2.5 text-right text-xs uppercase text-start tracking-wider w-12"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {filteredCases.map((caseItem) => (
                    <tr
                      key={caseItem.id}
                      className="hover:bg-slate-50 cursor-pointer transition-colors group"
                      onClick={() => navigate(`/cases/${caseItem.id}`)}
                    >
                      <td className="px-4 py-2.5">
                        <div className="p-1.5 bg-primary/10 rounded text-primary inline-flex">
                          <Briefcase className="h-3.5 w-3.5" />
                        </div>
                      </td>
                      <td className="px-2 py-2.5">
                        <div className="flex flex-col">
                          <span className="font-medium text-slate-900 text-sm truncate">
                            {caseItem.title}
                          </span>
                          <span className="text-xs text-slate-500">
                            #{caseItem.id}
                          </span>
                        </div>
                      </td>
                      <td className="px-2 py-2.5">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(caseItem.status)}`}
                        >
                          {getTranslatedStatus(caseItem.status)}
                        </span>
                      </td>
                      <td className="px-2 py-2.5 text-sm text-slate-700">
                        {caseItem.client_id
                          ? getClientName(caseItem.client_id)
                          : t("casesPage.noClient")}
                      </td>
                      <td className="px-2 py-2.5 text-xs text-slate-600">
                        {new Date(caseItem.created_at).toLocaleDateString(
                          "en-US",
                          { month: "short", day: "numeric", year: "numeric" },
                        )}
                      </td>
                      <td className="px-2 py-2.5 text-right relative">
                        <button
                          className="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600 opacity-0 group-hover:opacity-100 transition-all"
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenDropdownId(
                              openDropdownId === caseItem.id
                                ? null
                                : caseItem.id,
                            );
                          }}
                        >
                          <MoreVertical className="h-4 w-4" />
                        </button>
                        {openDropdownId === caseItem.id && (
                          <div
                            className="absolute right-0 top-full mt-1 w-44 bg-white border border-slate-200 rounded-lg shadow-lg z-50"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <div className="py-1">
                              <button
                                className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                onClick={() =>
                                  navigate(`/cases/${caseItem.id}`)
                                }
                              >
                                {t("casesPage.viewDetails")}
                              </button>
                              <button
                                className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                                onClick={() =>
                                  openAssignClientModal(caseItem.id)
                                }
                              >
                                <UserPlus className="h-3.5 w-3.5" />
                                {t("casesPage.assignClient")}
                              </button>
                              <hr className="my-1 border-slate-100" />
                              <button
                                className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                                onClick={() => {
                                  setOpenDropdownId(null);
                                  if (
                                    window.confirm(t("casesPage.deleteConfirm"))
                                  )
                                    showSnackbar(
                                      t("casesPage.deleteComingSoon"),
                                      { type: "info" },
                                    );
                                }}
                              >
                                {t("casesPage.deleteCase")}
                              </button>
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-slate-800">
                {t("casesPage.createNewCase")}
              </h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </div>
            <form onSubmit={handleCreateCase} className="space-y-4">
              <EntityVerification
                onVerified={(details) => {
                  setFormData((prev) => ({
                    ...prev,
                    title: prev.title
                      ? prev.title
                      : `${t("casesPage.caseTitle")} — ${details.name}`,
                    description: prev.description
                      ? prev.description
                      : details.address
                        ? `Entity Address: ${details.address}`
                        : "",
                  }));
                }}
              />
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                  {t("casesPage.caseTitle")}
                </label>
                <input
                  type="text"
                  required
                  value={formData.title}
                  onChange={(e) =>
                    setFormData({ ...formData, title: e.target.value })
                  }
                  className="w-full px-3 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm"
                  placeholder={t("casesPage.caseTitlePlaceholder")}
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                  {t("casesPage.description")}
                </label>
                <textarea
                  required
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  className="w-full px-3 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm resize-none"
                  rows={3}
                  placeholder={t("casesPage.briefDescPlaceholder")}
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                  {t("casesPage.clientOptional")}
                </label>
                <select
                  value={formData.client_id || ""}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      client_id: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                  className="w-full px-3 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm"
                >
                  <option value="">{t("casesPage.noClient")}</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.name} {client.email ? `(${client.email})` : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-medium hover:bg-slate-50 transition-colors"
                >
                  {t("casesPage.cancel")}
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="flex-1 px-4 py-2.5 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {creating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : null}
                  {creating
                    ? t("casesPage.creating")
                    : t("casesPage.createCaseBtn")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Assign Client Modal */}
      {showAssignClientModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-slate-800">
                {t("casesPage.assignClientModalTitle")}
              </h2>
              <button
                onClick={() => {
                  setShowAssignClientModal(false);
                  setSelectedCaseForAssignment(null);
                  setSelectedClientId(null);
                }}
                className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  {t("casesPage.selectClient")}
                </label>
                <select
                  value={selectedClientId || ""}
                  onChange={(e) => setSelectedClientId(Number(e.target.value))}
                  className="w-full px-3 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm"
                >
                  <option value="">{t("casesPage.chooseClient")}</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.name} {client.email ? `(${client.email})` : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowAssignClientModal(false);
                    setSelectedCaseForAssignment(null);
                    setSelectedClientId(null);
                  }}
                  className="flex-1 px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-medium hover:bg-slate-50 transition-colors"
                >
                  {t("casesPage.cancel")}
                </button>
                <button
                  onClick={handleAssignClient}
                  disabled={!selectedClientId || assigning}
                  className="flex-1 px-4 py-2.5 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {assigning ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : null}
                  {assigning
                    ? t("casesPage.assigning")
                    : t("casesPage.assignClient")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

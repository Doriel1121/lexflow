import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Briefcase, FileText, AlertCircle } from "lucide-react";
import api from "../../services/api";

interface StatCard {
  label: string;
  value: string;
  icon: React.ElementType;
  accent: string;
  description: string;
}

export function OverviewCards() {
  const { t } = useTranslation();
  const [stats, setStats] = useState({
    active_cases: 0,
    total_documents: 0,
    action_required: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await api.get("/v1/cases/stats");
      setStats(response.data);
    } catch {
      // silently fail - stats are informational
    } finally {
      setLoading(false);
    }
  };

  const cards: StatCard[] = [
    {
      label: t("dashboardPage.activeCases"),
      value: loading ? "—" : stats.active_cases.toString(),
      icon: Briefcase,
      accent: "text-blue-600",
      description: t("dashboardPage.activeCasesDesc"),
    },
    {
      label: t("dashboardPage.documents"),
      value: loading ? "—" : stats.total_documents.toString(),
      icon: FileText,
      accent: "text-emerald-600",
      description: t("dashboardPage.documentsDesc"),
    },
    {
      label: t("dashboardPage.actionRequired"),
      value: loading ? "—" : stats.action_required.toString(),
      icon: AlertCircle,
      accent: "text-amber-600",
      description: t("dashboardPage.actionRequiredDesc"),
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      {cards.map((card, i) => (
        <div
          key={i}
          className="bg-white rounded-2xl p-5 hover:shadow-md transition-shadow duration-200"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                {card.label}
              </p>
              <p className="text-3xl font-bold text-slate-800 mt-1.5">
                {card.value}
              </p>
              <p className="text-xs text-slate-400 mt-1">{card.description}</p>
            </div>
            <div className={`p-2 rounded-xl bg-slate-50 ${card.accent}`}>
              <card.icon className="h-5 w-5" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

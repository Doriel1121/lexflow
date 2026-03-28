import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import api from "../services/api";
import { Case, Document } from "../types";

const DashboardPage: React.FC = () => {
  const { t } = useTranslation();
  const [recentCases, setRecentCases] = useState<Case[]>([]);
  const [recentDocs, setRecentDocs] = useState<Document[]>([]);
  const [stats, setStats] = useState({
    totalCases: 0,
    totalDocs: 0,
    activeCases: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [casesRes, docsRes] = await Promise.all([
        api.get("/v1/cases/?skip=0&limit=5"),
        api.get("/v1/documents/?skip=0&limit=5"),
      ]);

      setRecentCases(casesRes.data.slice(0, 5));
      setRecentDocs(docsRes.data.slice(0, 5));

      setStats({
        totalCases: casesRes.data.length,
        activeCases: casesRes.data.filter((c: Case) => c.status === "open")
          .length,
        totalDocs: docsRes.data.length,
      });
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="p-4">{t("dashboardPage.loading")}</div>;
  }

  return (
    <div className="p-4">
      <h1 className="text-3xl font-bold mb-4">{t("dashboardPage.title")}</h1>
      <p className="mb-6">{t("dashboardPage.subtitle")}</p>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-2 text-gray-700 dark:text-gray-300">
            {t("dashboardPage.totalCases")}
          </h2>
          <p className="text-4xl font-bold text-blue-600">{stats.totalCases}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-2 text-gray-700 dark:text-gray-300">
            {t("dashboardPage.activeCases")}
          </h2>
          <p className="text-4xl font-bold text-green-600">
            {stats.activeCases}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-2 text-gray-700 dark:text-gray-300">
            {t("dashboardPage.documents")}
          </h2>
          <p className="text-4xl font-bold text-purple-600">
            {stats.totalDocs}
          </p>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">
              {t("dashboardPage.recentCases")}
            </h2>
            <Link
              to="/cases"
              className="text-blue-600 dark:text-blue-400 text-sm hover:underline"
            >
              {t("dashboardPage.viewAll")}
            </Link>
          </div>
          {recentCases.length > 0 ? (
            <ul className="space-y-3">
              {recentCases.map((c) => (
                <li
                  key={c.id}
                  className="border-l-4 border-blue-500 pl-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  <Link to={`/cases/${c.id}`}>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {c.title}
                    </p>
                    <p className="text-sm text-gray-500">
                      {t("dashboardPage.status")}:{" "}
                      <span
                        className={
                          c.status === "open"
                            ? "text-green-600"
                            : c.status === "pending"
                              ? "text-yellow-600"
                              : "text-red-600"
                        }
                      >
                        {c.status}
                      </span>
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500">{t("dashboardPage.noCases")}</p>
          )}
        </div>

        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">
              {t("dashboardPage.recentDocuments")}
            </h2>
            <Link
              to="/documents"
              className="text-blue-600 dark:text-blue-400 text-sm hover:underline"
            >
              {t("dashboardPage.viewAll")}
            </Link>
          </div>
          {recentDocs.length > 0 ? (
            <ul className="space-y-3">
              {recentDocs.map((doc) => (
                <li
                  key={doc.id}
                  className="border-l-4 border-purple-500 pl-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  <p className="font-medium text-gray-900 dark:text-white truncate">
                    {doc.filename}
                  </p>
                  <p className="text-sm text-gray-500">
                    Case #{doc.case_id} •{" "}
                    {doc.classification || t("documentsPage.unclassified")}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500">{t("dashboardPage.noDocuments")}</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;

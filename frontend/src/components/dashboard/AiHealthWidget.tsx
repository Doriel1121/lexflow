import { useEffect, useState } from 'react';
import { Bot, AlertTriangle, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import api from '../../services/api';
import type { OrgAiHealth } from '../../types';

export function AiHealthWidget() {
  const { t } = useTranslation();
  const [data, setData] = useState<OrgAiHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get('/v1/org/analytics/ai-health');
        setData(res.data);
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl p-6 border border-slate-100 animate-pulse h-48" />
    );
  }

  if (!data) return null;

  const needsAttention =
    data.completed_without_ai > 0 ||
    data.embedding_issues > 0 ||
    data.failed_documents > 0;

  return (
    <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-violet-50 text-violet-600">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-800">{t('aiHealth.title')}</h3>
            <p className="text-[11px] text-slate-400">
              {t('aiHealth.provider', { provider: data.provider })}
            </p>
          </div>
        </div>
        <span
          className={`text-xs font-semibold px-2 py-1 rounded-full ${
            data.health_score_percent >= 85
              ? 'bg-emerald-50 text-emerald-700'
              : data.health_score_percent >= 60
                ? 'bg-amber-50 text-amber-700'
                : 'bg-red-50 text-red-700'
          }`}
        >
          {t('aiHealth.score', { score: data.health_score_percent })}
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <Stat label={t('aiHealth.processing')} value={data.processing_now} />
        <Stat label={t('aiHealth.withoutAi')} value={data.completed_without_ai} warn />
        <Stat label={t('aiHealth.embeddingIssues')} value={data.embedding_issues} warn />
        <Stat label={t('aiHealth.errors7d')} value={data.processing_errors_7d} warn />
      </div>

      <div className="flex flex-wrap gap-2 text-[11px] text-slate-500 mb-3">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-50">
          <Sparkles className="h-3 w-3" />
          {t('aiHealth.chunkedDocs', { count: data.chunked_analysis_documents })}
        </span>
        <span className="px-2 py-0.5 rounded bg-slate-50">
          {t('aiHealth.embedFailRate', { rate: data.embedding_failure_rate_percent })}
        </span>
      </div>

      {needsAttention && data.recent_errors.length > 0 && (
        <div className="border-t border-slate-100 pt-3">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
            {t('aiHealth.recentErrors')}
          </p>
          <ul className="space-y-1.5 max-h-28 overflow-y-auto">
            {data.recent_errors.map((err, i) => (
              <li key={i} className="text-xs text-slate-600 flex gap-2">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
                <span>
                  <span className="font-medium">{err.filename}</span>
                  {' — '}
                  {err.stage}: {err.message}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  warn,
}: {
  label: string;
  value: number;
  warn?: boolean;
}) {
  return (
    <div className="rounded-xl bg-slate-50 px-3 py-2">
      <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">{label}</p>
      <p
        className={`text-lg font-bold mt-0.5 ${
          warn && value > 0 ? 'text-amber-700' : 'text-slate-800'
        }`}
      >
        {value}
      </p>
    </div>
  );
}

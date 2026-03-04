import React, { useState } from 'react';
import { Search, ShieldAlert, ShieldCheck, Loader2 } from 'lucide-react';
import api from '../../services/api';

interface RiskDetails {
  query: string;
  auto_fill_name?: string;
  auto_fill_address?: string;
  is_high_risk: boolean;
  warnings: string[];
  local_risk?: {
    is_high_risk: boolean;
    status: string;
    risk_reason?: string;
  };
  global_risk?: {
    is_high_risk: boolean;
    risk_reason?: string;
  };
}

interface EntityVerificationProps {
  onVerified: (details: { name: string; address?: string }) => void;
}

export const EntityVerification: React.FC<EntityVerificationProps> = ({ onVerified }) => {
  const [query, setQuery] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [result, setResult] = useState<RiskDetails | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleVerify = async () => {
    if (!query.trim()) return;
    
    setVerifying(true);
    setResult(null);
    setError(null);

    try {
      const response = await api.get<RiskDetails>(`/v1/risk/verify?query=${encodeURIComponent(query)}`);
      const details = response.data;
      setResult(details);
      
      if (details.auto_fill_name) {
        onVerified({
          name: details.auto_fill_name,
          address: details.auto_fill_address
        });
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Verification failed. Service may be unavailable.');
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="space-y-4 mb-6 border border-slate-200 rounded-xl p-5 bg-slate-50/50">
      <div className="flex flex-col space-y-1.5 mb-2">
        <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
          Entity Risk Radar & Auto-fill
        </h3>
        <p className="text-xs text-slate-500">
          Enter an Israeli Company ID or Entity Name. We'll automatically verify against local registries and global AML/KYC sanctions lists.
        </p>
      </div>
      
      <div className="flex gap-3">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-4 w-4 text-slate-400" />
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleVerify()}
            className="w-full pl-9 pr-3 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm bg-white"
            placeholder="e.g. 512345678 or Acme Corp"
          />
        </div>
        <button
          type="button"
          onClick={handleVerify}
          disabled={verifying || !query.trim()}
          className="px-4 py-2.5 bg-slate-800 text-white rounded-xl text-sm font-medium hover:bg-slate-700 transition-colors disabled:opacity-50 flex items-center gap-2 whitespace-nowrap"
        >
          {verifying && <Loader2 className="h-4 w-4 animate-spin" />}
          Vefiry Entity
        </button>
      </div>

      {error && (
        <div className="text-xs text-red-500 font-medium">
          {error}
        </div>
      )}

      {result && (
        <div className="animate-in fade-in slide-in-from-top-2 duration-300">
          {!result.is_high_risk ? (
             <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 flex gap-3 text-emerald-800 text-sm">
                <ShieldCheck className="h-5 w-5 text-emerald-500 shrink-0" />
                <div>
                   <p className="font-medium">Verification Passed — Low Risk</p>
                   {result.auto_fill_name && (
                      <p className="text-emerald-700 text-xs mt-1">
                        Found Entity: <strong>{result.auto_fill_name}</strong>
                      </p>
                   )}
                </div>
             </div>
          ) : (
             <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex gap-3 text-red-900 text-sm">
                <ShieldAlert className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
                <div className="space-y-2">
                   <p className="font-bold text-red-700">⚠️ High Risk Entity Detected</p>
                   
                   {result.local_risk?.is_high_risk && (
                      <div className="text-xs bg-red-100/50 p-2 rounded">
                         <span className="font-semibold block mb-0.5">Local Registry Alert:</span>
                         Status is <strong>{result.local_risk.status}</strong>. {result.local_risk.risk_reason}
                      </div>
                   )}
                   
                   {result.global_risk?.is_high_risk && (
                      <div className="text-xs bg-red-100/50 p-2 rounded">
                         <span className="font-semibold block mb-0.5">Global AML/KYC Sanctions Alert:</span>
                         {result.global_risk.risk_reason}
                      </div>
                   )}
                   
                   {!result.local_risk?.is_high_risk && !result.global_risk?.is_high_risk && (
                      <div className="text-xs">
                         This entity was flagged for manual review reasons. {result.warnings.join(", ")}
                      </div>
                   )}
                </div>
             </div>
          )}
        </div>
      )}
    </div>
  );
};

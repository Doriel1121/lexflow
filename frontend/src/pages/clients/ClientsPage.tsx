import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, ShieldAlert, ShieldCheck, Building2, Phone, Mail } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { clientsService, Client } from '../../services/clients';

export const ClientsPage: React.FC = () => {
  const { t } = useTranslation();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchClients();
  }, []);

  const fetchClients = async () => {
    try {
      const data = await clientsService.getClients();
      setClients(data);
    } catch (error) {
      console.error('Failed to fetch clients:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto py-6">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">{t('clients.title')}</h1>
          <p className="text-sm text-slate-500 mt-1">{t('clients.subtitle')}</p>
        </div>
        <Link
          to="/clients/new"
          className="bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2.5 rounded-lg flex items-center gap-2 text-sm font-medium transition-colors"
        >
          <Plus className="h-4 w-4" />
          {t('clients.addClient')}
        </Link>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        {clients.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <Building2 className="h-12 w-12 mx-auto mb-4 text-slate-300 opacity-50" />
            <h3 className="font-semibold text-slate-800 mb-1">{t('clients.noClients')}</h3>
            <p className="text-sm">{t('clients.noClientsDesc')}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-medium">
                <tr>
                  <th className="px-6 py-4">{t('clients.table.clientName')}</th>
                  <th className="px-6 py-4">{t('clients.table.contact')}</th>
                  <th className="px-6 py-4">{t('clients.table.riskStatus')}</th>
                  <th className="px-6 py-4">{t('clients.table.addedOn')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {clients.map((client) => (
                  <tr key={client.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-medium text-slate-800">{client.name}</div>
                      {client.address && <div className="text-xs text-slate-500 mt-0.5 truncate max-w-[200px]">{client.address}</div>}
                    </td>
                    <td className="px-6 py-4">
                      {client.contact_person ? (
                        <div className="space-y-1">
                          <div className="text-slate-800">{client.contact_person}</div>
                          {client.contact_email && (
                            <div className="flex items-center gap-1.5 text-xs text-slate-500">
                              <Mail className="h-3 w-3" /> {client.contact_email}
                            </div>
                          )}
                          {client.phone_number && (
                            <div className="flex items-center gap-1.5 text-xs text-slate-500">
                              <Phone className="h-3 w-3" /> {client.phone_number}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-400 italic text-xs">{t('clients.noContactInfo')}</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {client.is_high_risk ? (
                        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-700">
                          <ShieldAlert className="h-3.5 w-3.5" /> {t('clients.highRisk')}
                        </div>
                      ) : (
                        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
                          <ShieldCheck className="h-3.5 w-3.5" /> {t('clients.verified')}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-500">
                      {new Date(client.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

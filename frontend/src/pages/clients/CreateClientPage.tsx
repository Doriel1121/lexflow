import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { EntityVerification } from '../../components/cases/EntityVerification';
import { clientsService, ClientCreate } from '../../services/clients';
import { ShieldAlert, ShieldCheck } from 'lucide-react';

export const CreateClientPage: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<ClientCreate>({
    name: '',
    contact_person: '',
    contact_email: '',
    phone_number: '',
    address: '',
    is_high_risk: false,
    risk_notes: '',
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleEntityVerified = (details: any) => {
    // details is expected to have name, address, is_high_risk, warnings, local_risk, global_risk based on the Risk Radar output
    const riskNotes: string[] = [];
    if (details.warnings && details.warnings.length > 0) {
        riskNotes.push(...details.warnings);
    }
    if (details.local_risk?.risk_reason) {
        riskNotes.push(`Local: ${details.local_risk.risk_reason}`);
    }
    if (details.global_risk?.risk_reason) {
        riskNotes.push(`Global: ${details.global_risk.risk_reason}`);
    }

    setFormData(prev => ({
      ...prev,
      name: details.name || details.auto_fill_name || prev.name,
      address: details.address || details.auto_fill_address || prev.address,
      is_high_risk: details.is_high_risk || false,
      risk_notes: riskNotes.join(' | ')
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name) {
      setError("Company Name is required.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await clientsService.createClient(formData);
      navigate('/clients');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to create client');
      setLoading(false);
    }
  };

  return (
    <div className="p-4 max-w-2xl mx-auto py-8">
      <div className="mb-6">
        <Link to="/clients" className="text-primary hover:underline text-sm font-medium flex items-center gap-1">
          &larr; Back to Clients
        </Link>
      </div>

      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Onboard New Client</h1>
        <p className="text-slate-500 mt-2">Verify the entity's risk profile before creation.</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl mb-6 text-sm flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* STEP 1: MUST RUN RISK RADAR TO AUTO-FILL DATA */}
      <EntityVerification 
        onVerified={(details) => handleEntityVerified(details)} 
      />

      <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-xl shadow-sm p-6 mt-6 space-y-5">
        
        {/* Risk Status Indicator (Read Only Display) */}
        <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
          <span className="text-sm font-medium text-slate-700">Risk Assessment:</span>
          {formData.is_high_risk ? (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-700">
              <ShieldAlert className="h-3.5 w-3.5" /> High Risk Detected
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
              <ShieldCheck className="h-3.5 w-3.5" /> Cleared
            </div>
          )}
        </div>

        {formData.risk_notes && (
            <div className="text-xs text-slate-500 bg-slate-50 p-3 rounded-lg border border-slate-200">
                <strong>Notes:</strong> {formData.risk_notes}
            </div>
        )}

        <div>
          <label className="block text-slate-700 text-sm font-semibold mb-1.5">Official Entity Name *</label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:border-primary text-sm"
            placeholder="Legal name of standard entity"
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-slate-700 text-sm font-semibold mb-1.5">Primary Contact Person</label>
            <input
              type="text"
              name="contact_person"
              value={formData.contact_person}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:border-primary text-sm"
              placeholder="Full name"
            />
          </div>
          <div>
            <label className="block text-slate-700 text-sm font-semibold mb-1.5">Contact Email</label>
            <input
              type="email"
              name="contact_email"
              value={formData.contact_email}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:border-primary text-sm"
              placeholder="email@example.com"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
            <div>
                <label className="block text-slate-700 text-sm font-semibold mb-1.5">Phone Number</label>
                <input
                type="tel"
                name="phone_number"
                value={formData.phone_number}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:border-primary text-sm"
                placeholder="+1 (555) 000-0000"
                />
            </div>
            <div>
                <label className="block text-slate-700 text-sm font-semibold mb-1.5">Registered Address</label>
                <input
                type="text"
                name="address"
                value={formData.address}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:border-primary text-sm"
                placeholder="123 Corporate Blvd"
                />
            </div>
        </div>

        <div className="pt-4 flex items-center justify-end gap-3 border-t border-slate-100">
          <Link
            to="/clients"
            className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={loading}
            className="bg-primary hover:bg-primary/90 text-white font-semibold py-2 px-5 rounded-lg transition-colors disabled:opacity-50"
          >
            {loading ? 'Creating...' : 'Save Client to Database'}
          </button>
        </div>
      </form>
    </div>
  );
};

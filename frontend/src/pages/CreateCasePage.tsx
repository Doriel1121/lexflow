import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api from '../services/api';
import { clientsService, Client } from '../services/clients';
import { ShieldAlert, ShieldCheck } from 'lucide-react';

const CreateCasePage: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    status: 'open' as 'open' | 'closed' | 'pending',
    client_id: '',
  });
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    const fetchClients = async () => {
      try {
        const data = await clientsService.getClients();
        setClients(data);
      } catch (err) {
        console.error("Failed to load clients", err);
      }
    };
    fetchClients();
  }, []);

  const selectedClient = clients.find(c => c.id.toString() === formData.client_id);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        ...formData,
        client_id: parseInt(formData.client_id),
      };
      const response = await api.post('/v1/cases/', payload);
      navigate(`/cases/${response.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to create case');
      setLoading(false);
    }
  };

  return (
    <div className="p-4 max-w-2xl mx-auto">
      <div className="mb-4">
        <Link to="/cases" className="text-blue-600 dark:text-blue-400">&larr; Back to cases</Link>
      </div>
      
      <h1 className="text-3xl font-bold mb-6">Create New Case</h1>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          <strong>Error:</strong> {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        
        <div className="mb-4">
          <label htmlFor="client_id" className="block text-gray-700 dark:text-gray-300 text-sm font-bold mb-2">
            Client *
          </label>
          <select
            id="client_id"
            name="client_id"
            value={formData.client_id}
            onChange={handleChange}
            className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline dark:bg-gray-700 dark:text-white dark:border-gray-600 bg-white"
            required
          >
            <option value="" disabled>Select a verified client...</option>
            {clients.map(client => (
              <option key={client.id} value={client.id}>
                {client.name} {client.is_high_risk ? '(High Risk)' : ''}
              </option>
            ))}
          </select>
          {selectedClient && (
            <div className="mt-3 flex items-center gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100 dark:bg-slate-700 dark:border-slate-600">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">Entity Risk Profile:</span>
              {selectedClient.is_high_risk ? (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-700">
                  <ShieldAlert className="h-3.5 w-3.5" /> High Risk Detected
                </div>
              ) : (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
                  <ShieldCheck className="h-3.5 w-3.5" /> Verified Clean
                </div>
              )}
            </div>
          )}
        </div>

        <div className="mb-4">
          <label htmlFor="title" className="block text-gray-700 dark:text-gray-300 text-sm font-bold mb-2">
            Case Title *
          </label>
          <input
            type="text"
            id="title"
            name="title"
            value={formData.title}
            onChange={handleChange}
            className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline dark:bg-gray-700 dark:text-white dark:border-gray-600"
            placeholder="Enter case title"
            required
          />
        </div>

        <div className="mb-4">
          <label htmlFor="description" className="block text-gray-700 dark:text-gray-300 text-sm font-bold mb-2">
            Description
          </label>
          <textarea
            id="description"
            name="description"
            value={formData.description}
            onChange={handleChange}
            rows={4}
            className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline dark:bg-gray-700 dark:text-white dark:border-gray-600"
            placeholder="Enter case description"
          />
        </div>

        <div className="mb-6">
          <label htmlFor="status" className="block text-gray-700 dark:text-gray-300 text-sm font-bold mb-2">
            Status *
          </label>
          <select
            id="status"
            name="status"
            value={formData.status}
            onChange={handleChange}
            className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline dark:bg-gray-700 dark:text-white dark:border-gray-600"
            required
          >
            <option value="open">Open</option>
            <option value="pending">Pending</option>
            <option value="closed">Closed</option>
          </select>
        </div>

        <div className="flex items-center justify-between">
          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50"
          >
            {loading ? 'Creating...' : 'Create Case'}
          </button>
          <Link
            to="/cases"
            className="text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
};

export default CreateCasePage;

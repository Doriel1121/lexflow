import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { Case } from '../types';

const CasesPage: React.FC = () => {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCases();
  }, []);

  const fetchCases = async () => {
    try {
      setLoading(true);
      const response = await api.get('/v1/cases/');
      setCases(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching cases:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to fetch cases');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="p-4">Loading cases...</div>;
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          <strong>Error:</strong> {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h1 className="text-3xl font-bold mb-4">Cases</h1>
      <div className="flex justify-between items-center mb-4">
        <p>Manage your legal cases.</p>
        <Link to="/cases/new" className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
          Create New Case
        </Link>
      </div>
      
      {cases.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 text-center">
          <p className="text-gray-600 dark:text-gray-400">No cases found. Create your first case to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cases.map((caseItem) => (
            <div key={caseItem.id} className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white">{caseItem.title}</h3>
                <span className={`px-2 py-1 text-xs font-semibold rounded ${
                  caseItem.status === 'open' ? 'bg-green-100 text-green-800' : 
                  caseItem.status === 'pending' ? 'bg-yellow-100 text-yellow-800' : 
                  'bg-red-100 text-red-800'
                }`}>
                  {caseItem.status.toUpperCase()}
                </span>
              </div>
              <p className="text-gray-600 dark:text-gray-400 text-sm mb-3">
                {caseItem.description || 'No description'}
              </p>
              <div className="text-sm text-gray-500 dark:text-gray-500 mb-3">
                <p>Case ID: #{caseItem.id}</p>
                <p>Client ID: {caseItem.client_id}</p>
              </div>
              <div className="flex justify-between items-center">
                <div className="text-xs text-gray-500">
                  {caseItem.notes?.length || 0} notes • {caseItem.documents?.length || 0} docs
                </div>
                <Link 
                  to={`/cases/${caseItem.id}`} 
                  className="text-blue-600 dark:text-blue-400 hover:text-blue-800 font-medium"
                >
                  View Details →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CasesPage;

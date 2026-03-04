import { useState } from 'react';

function TestAIServices() {
  const [responseData, setResponseData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleTestClick = async () => {
    setLoading(true);
    setError(null);
    try {
      // Ensure this URL matches where your backend is running
      const response = await fetch('http://localhost:8000/test-ai-services');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setResponseData(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>Test AI Services</h1>
      <button onClick={handleTestClick} disabled={loading}>
        {loading ? 'Testing...' : 'Run AI Services Test'}
      </button>
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {responseData && (
        <div>
          <h2>Response:</h2>
          <pre>{JSON.stringify(responseData, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default TestAIServices;

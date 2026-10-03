import React, { useState } from 'react';

export default function App() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    const form = new FormData(event.currentTarget);
    try {
      let response = await fetch('/api/drift/calculate', { method: 'POST', body: form });
      if (response.status === 404) {
        response = await fetch('/api/health');
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Request failed');
      setResult(data);
    } catch (err) {
      setError(err.message || 'Start the backend, then retry.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>TerraState Guardian</h1>
      <p>Upload files or call the API from this page. Keep the backend running.</p>
      <form onSubmit={onSubmit}>
        <p><label>Baseline<br /><input type="file" name="baseline" accept=".csv" /></label></p>
        <p><label>Comparison<br /><input type="file" name="comparison" accept=".csv" /></label></p>
        <button type="submit" disabled={busy}>{busy ? 'Working…' : 'Run analysis'}</button>
      </form>
      {error ? <p>{error}</p> : null}
      {result ? <pre>{JSON.stringify(result, null, 2)}</pre> : null}
    </main>
  );
}

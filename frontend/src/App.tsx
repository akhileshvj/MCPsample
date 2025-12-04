import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';

interface ApiResponse {
  sql: string;
  rows: Record<string, unknown>[];
  columns: string[];
  raw_answer?: string | null;
  summary?: string | null;
}

export const App: React.FC = () => {
  const [dbPath, setDbPath] = useState('C\\\\Users\\\\GenAIKOCVISUSR53\\\\Documents\\\\hackathon\\\\sample.db');
  const [question, setQuestion] = useState('Show all customers with their total order amount, sorted by total amount descending');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<ApiResponse | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const res = await fetch('/api/nl-query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          db_path: dbPath,
          question,
          dialect: 'sqlite',
          max_tokens: 512,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed with status ${res.status}`);
      }

      const data: ApiResponse = await res.json();
      setResponse(data);
    } catch (err: any) {
      setError(err.message ?? 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-root">
      <div className="gradient-bg" />
      <header className="app-header">
        <div className="logo-circle">NL</div>
        <div>
          <h1 className="title">Lovable NL → SQL Playground</h1>
          <p className="subtitle">Ask questions in natural language. See the SQL and live results from your SQLite database.</p>
        </div>
      </header>

      <main className="app-main">
        <section className="card input-card">
          <h2 className="card-title">Ask your database</h2>
          <form className="form" onSubmit={handleSubmit}>
            <label className="field">
              <span className="field-label">SQLite DB path</span>
              <input
                type="text"
                value={dbPath}
                onChange={(e) => setDbPath(e.target.value)}
                className="input"
                placeholder="C:\\path\\to\\your.db"
              />
            </label>

            <label className="field">
              <span className="field-label">Your question</span>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                className="textarea"
                rows={3}
                placeholder="e.g. Show total sales per city for 2024"
              />
            </label>

            <button className="primary-btn" type="submit" disabled={loading}>
              {loading ? 'Thinking with SQL…' : 'Run query'}
            </button>
          </form>

          {error && <div className="error-banner">{error}</div>}
        </section>

        <section className="card results-card">
          <h2 className="card-title">Results</h2>
          {!response && !error && !loading && (
            <p className="placeholder">Run a query to see generated SQL and data here.</p>
          )}

          {response && (
            <>
              <div className="sql-block">
                <div className="section-label">Generated SQL</div>
                <pre><code>{response.sql}</code></pre>
              </div>

              <div className="table-wrapper">
                <div className="section-label">Rows ({response.rows.length})</div>
                {response.rows.length === 0 ? (
                  <p className="placeholder">No rows returned.</p>
                ) : (
                  <table className="results-table">
                    <thead>
                      <tr>
                        {response.columns.map((col) => (
                          <th key={col}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {response.rows.map((row, idx) => (
                        <tr key={idx}>
                          {response.columns.map((col) => (
                            <td key={col}>{String((row as any)[col] ?? '')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {response.summary && (
                <div style={{ marginTop: 16 }}>
                  <div className="section-label">Markdown table</div>
                  <div className="table-wrapper">
                    <ReactMarkdown>{response.summary}</ReactMarkdown>
                  </div>
                </div>
              )}
            </>
          )}
        </section>
      </main>

      <footer className="app-footer">
        <span>Powered by SQLite + FastAPI + React</span>
      </footer>
    </div>
  );
};

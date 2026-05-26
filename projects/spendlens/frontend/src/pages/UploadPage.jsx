import React, { useState } from "react";
import { analyseStatement, loadDemoReport, ApiError } from "../api.js";
import { SkeletonLoader } from "../components/SkeletonLoader.jsx";

export function UploadPage({ onReport, onError }) {
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      onError?.("Please choose a PDF or CSV file.");
      return;
    }
    setLoading(true);
    onError?.(null);
    try {
      const report = await analyseStatement(file);
      onReport?.(report);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : err?.message || "Upload failed — is the API running?";
      onError?.(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setLoading(true);
    onError?.(null);
    try {
      const data = await loadDemoReport();
      onReport?.(data);
    } catch (err) {
      onError?.(err instanceof ApiError ? err.message : err?.message || "Demo failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <div className="card">
        <h1>SpendLens</h1>
        <p className="sub">Your money, clearly.</p>
        <p className="note">Your data is processed locally. Never stored.</p>
        <form onSubmit={handleSubmit}>
          <label
            style={{
              display: "block",
              textAlign: "left",
              marginBottom: 8,
              fontSize: "0.85rem",
              color: "var(--muted)",
            }}
          >
            Upload your bank statement (PDF or CSV)
          </label>
          <input
            type="file"
            accept=".pdf,.csv"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            required
            disabled={loading}
          />
          <button type="submit" className="primary" disabled={loading}>
            {loading ? "Analysing…" : "Analyse"}
          </button>
        </form>

        <div style={{ marginTop: 12 }}>
          <button type="button" className="secondary" onClick={handleDemo} disabled={loading}>
            Try with sample data
          </button>
        </div>

        {loading ? (
          <div style={{ marginTop: 16 }}>
            <SkeletonLoader lines={6} />
          </div>
        ) : null}
      </div>
    </div>
  );
}


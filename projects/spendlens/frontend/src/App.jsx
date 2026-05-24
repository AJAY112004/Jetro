import { useCallback, useState } from "react";
import {
  Chart as ChartJS,
  ArcElement,
  CategoryScale,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { Doughnut, Line } from "react-chartjs-2";
import { analyseStatement, loadDemoReport, pdfDownloadUrl, ApiError } from "./api.js";

ChartJS.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

const PALETTE = [
  "#3b82f6", "#22c55e", "#ef4444", "#eab308", "#a855f7",
  "#f97316", "#06b6d4", "#ec4899", "#84cc16", "#64748b",
];

function fmt(n) {
  return `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function UploadView({ onReport, onError }) {
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      onError("Please choose a PDF or CSV file.");
      return;
    }
    setLoading(true);
    onError(null);
    try {
      if (import.meta.env.DEV) {
        console.log("[App] uploading file:", file.name, file.size, "bytes");
      }
      const report = await analyseStatement(file);
      onReport(report);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err?.message || "Upload failed — is Flask running on port 5050?";
      if (import.meta.env.DEV) {
        console.error("[App] upload failed:", err);
        if (err instanceof ApiError && err.detail) {
          console.error("[App] server detail:\n", err.detail);
        }
      }
      onError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setLoading(true);
    onError(null);
    try {
      const report = await loadDemoReport();
      onReport(report);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : err.message || "Demo failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h1>SpendLens</h1>
      <p className="sub">Your money, clearly.</p>
      <p className="note">Your data is processed locally. Never stored.</p>
      <form onSubmit={handleSubmit}>
        <label style={{ display: "block", textAlign: "left", marginBottom: 8, fontSize: "0.85rem", color: "#94a3b8" }}>
          Upload your bank statement (PDF or CSV)
        </label>
        <input
          type="file"
          accept=".pdf,.csv"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          required
        />
        <button type="submit" className="primary" disabled={loading}>
          {loading ? "Analysing…" : "Analyse"}
        </button>
      </form>
      {/* <button type="button" className="link" onClick={handleDemo} disabled={loading}>
        Try with sample data →
      </button> */}
    </div>
  );
}

function ResultsView({ report, onBack }) {
  if (!report || typeof report !== "object") {
    return (
      <div className="app">
        <p className="error">Invalid report data from server.</p>
        <button type="button" className="secondary" onClick={onBack}>← Back</button>
      </div>
    );
  }

  const s = report.spend_summary || {};
  const sc = report.savings_score || {};
  const cats = report.category_breakdown || [];
  const trend = report.daily_spend_trend || [];

  const donutData = {
    labels: cats.map((c) => c.category),
    datasets: [{ data: cats.map((c) => c.amount), backgroundColor: PALETTE }],
  };

  const lineData = {
    labels: trend.map((d) => (d.date || "").slice(5)),
    datasets: [
      {
        label: "Daily spend",
        data: trend.map((d) => d.spend),
        borderColor: "#3b82f6",
        backgroundColor: "rgba(59,130,246,0.2)",
        fill: true,
        tension: 0.3,
      },
    ],
  };

  const chartOpts = {
    plugins: { legend: { labels: { color: "#94a3b8" } } },
    scales: {
      x: { ticks: { color: "#94a3b8" }, grid: { color: "#334155" } },
      y: { ticks: { color: "#94a3b8" }, grid: { color: "#334155" } },
    },
  };

  return (
    <div className="app">
      <div className="header">
        <h1>SpendLens — Analysis</h1>
        <p>{report.month_label}</p>
      </div>

      <div className="kpis">
        <div className="kpi inc">
          <div className="lbl">Total Income</div>
          <div className="val">{fmt(s.total_income)}</div>
        </div>
        <div className="kpi exp">
          <div className="lbl">Total Expenses</div>
          <div className="val">{fmt(s.total_expenses)}</div>
        </div>
        <div className="kpi sav">
          <div className="lbl">Net Savings</div>
          <div className="val">{fmt(s.net_savings)}</div>
        </div>
        <div className="kpi">
          <div className="lbl">Savings Score</div>
          <div className="val">{sc.score}/100</div>
          <span
            className="badge"
            style={{ background: `${sc.colour}33`, color: sc.colour }}
          >
            {sc.label}
          </span>
        </div>
      </div>

      <div className="charts">
        <div className="panel">
          <h2>Category breakdown</h2>
          <div className="chart-wrap">
            <Doughnut data={donutData} options={{ plugins: { legend: { position: "bottom" } } }} />
          </div>
        </div>
        <div className="panel">
          <h2>Daily spend trend</h2>
          <div className="chart-wrap">
            <Line data={lineData} options={chartOpts} />
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>⚠ Anomaly alerts</h2>
        {(report.anomalies || []).length === 0 && (
          <p style={{ color: "#94a3b8" }}>No anomalies flagged.</p>
        )}
        {(report.anomalies || []).map((a, i) => (
          <div className="row-item" key={i}>
            <span>⚠</span>
            <span>{a.message}</span>
          </div>
        ))}
      </div>

      <div className="panel">
        <h2>💡 AI insights</h2>
        {(report.ai_insights || []).map((t, i) => (
          <div className="row-item" key={i}>
            <span>💡</span>
            <span>{t}</span>
          </div>
        ))}
      </div>

      <div className="rebal">
        <strong>Rebalancing:</strong> {report.rebalancing_recommendation}
      </div>

      <div className="actions">
        <a className="primary" href={pdfDownloadUrl()} target="_blank" rel="noreferrer">
          Download Report (PDF)
        </a>
        <button type="button" className="secondary" onClick={onBack}>
          ← Upload another
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  const handleBack = useCallback(() => {
    setReport(null);
    setError(null);
  }, []);

  if (report) {
    return <ResultsView report={report} onBack={handleBack} />;
  }

  return (
    <div className="app">
      {error && <div className="error" style={{ maxWidth: 480, margin: "20px auto" }}>{error}</div>}
      <UploadView onReport={setReport} onError={setError} />
    </div>
  );
}

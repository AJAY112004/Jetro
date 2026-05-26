import React, { useMemo, useState } from "react";
import { Doughnut, Line, Chart as ChartJS } from "react-chartjs-2";
import {
  ArcElement,
  CategoryScale,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { downloadReportPdf, ApiError } from "../api.js";
import { SkeletonLoader } from "../components/SkeletonLoader.jsx";

ChartJS.register(ArcElement, CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

const PALETTE = ["#3b82f6", "#22c55e", "#ef4444", "#eab308", "#a855f7", "#f97316", "#06b6d4", "#ec4899"];

function fmt(n) {
  return `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function ResultsPage({ report, onBack, onError }) {
  const [pdfLoading, setPdfLoading] = useState(false);

  const s = report?.spend_summary || {};
  const sc = report?.savings_score || {};
  const cats = report?.category_breakdown || [];
  const trend = report?.daily_spend_trend || [];

  const donutData = useMemo(() => {
    return {
      labels: cats.map((c) => c.category),
      datasets: [{ data: cats.map((c) => c.amount), backgroundColor: PALETTE }],
    };
  }, [cats]);

  const lineData = useMemo(() => {
    return {
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
  }, [trend]);

  const chartOpts = useMemo(() => {
    return {
      plugins: { legend: { labels: { color: "var(--muted)" } } },
      scales: {
        x: { ticks: { color: "var(--muted)" }, grid: { color: "var(--grid)" } },
        y: { ticks: { color: "var(--muted)" }, grid: { color: "var(--grid)" } },
      },
    };
  }, []);

  const handleDownloadPdf = async () => {
    setPdfLoading(true);
    onError?.(null);
    try {
      await downloadReportPdf();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : err?.message || "PDF download failed.";
      onError?.(msg);
    } finally {
      setPdfLoading(false);
    }
  };

  if (!report || typeof report !== "object") {
    return (
      <div className="app">
        <p className="error">Invalid report data from server.</p>
        <button type="button" className="secondary" onClick={onBack}>
          ← Back
        </button>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="header">
        <h1>SpendLens — Analysis</h1>
        <p>{report.month_label}</p>
      </div>

      {onError ? (
        <div className="error" style={{ maxWidth: 720, margin: "12px auto" }}>
          {onError}
        </div>
      ) : null}

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
          <span className="badge" style={{ background: `${sc.colour}33`, color: sc.colour }}>
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
        {(report.anomalies || []).length === 0 ? (
          <p style={{ color: "var(--muted)" }}>No anomalies flagged.</p>
        ) : (
          (report.anomalies || []).map((a, i) => (
            <div className="row-item" key={i}>
              <span>⚠</span>
              <span>{a.message}</span>
            </div>
          ))
        )}
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
        <button type="button" className="primary" onClick={handleDownloadPdf} disabled={pdfLoading}>
          {pdfLoading ? "Preparing PDF…" : "Download Report (PDF)"}
        </button>
        <button type="button" className="secondary" onClick={onBack} disabled={pdfLoading}>
          ← Upload another
        </button>
      </div>

      {pdfLoading ? (
        <div style={{ marginTop: 14 }}>
          <SkeletonLoader lines={4} />
        </div>
      ) : null}
    </div>
  );
}


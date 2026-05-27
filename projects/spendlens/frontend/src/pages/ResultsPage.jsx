import React, { useMemo, useState } from "react";
import { Doughnut, Line } from "react-chartjs-2";

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

import { downloadReportPdf, ApiError } from "../api.js";
import { SkeletonLoader } from "../components/SkeletonLoader.jsx";

// Register chart components
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
  "#3b82f6",
  "#22c55e",
  "#ef4444",
  "#eab308",
  "#a855f7",
  "#f97316",
  "#06b6d4",
  "#ec4899",
];

function fmt(value) {
  return `₹${Number(value || 0).toLocaleString("en-IN", {
    maximumFractionDigits: 0,
  })}`;
}

export function ResultsPage({ report, onBack, onError }) {
  const [pdfLoading, setPdfLoading] = useState(false);

  const summary = report?.spend_summary ?? {};
  const score = report?.savings_score ?? {};
  const categories = report?.category_breakdown ?? [];
  const trend = report?.daily_spend_trend ?? [];

  const donutData = useMemo(
    () => ({
      labels: categories.map((c) => c.category),
      datasets: [
        {
          data: categories.map((c) => c.amount),
          backgroundColor: PALETTE,
          borderWidth: 0,
        },
      ],
    }),
    [categories]
  );

  const lineData = useMemo(
    () => ({
      labels: trend.map((d) => (d.date || "").slice(5)),
      datasets: [
        {
          label: "Daily Spend",
          data: trend.map((d) => d.spend),
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59,130,246,.2)",
          fill: true,
          tension: 0.3,
        },
      ],
    }),
    [trend]
  );

  const chartOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,

      plugins: {
        legend: {
          labels: {
            color: "#94a3b8",
          },
        },
      },

      scales: {
        x: {
          ticks: {
            color: "#94a3b8",
          },
          grid: {
            color: "#334155",
          },
        },

        y: {
          ticks: {
            color: "#94a3b8",
          },
          grid: {
            color: "#334155",
          },
        },
      },
    }),
    []
  );

  async function handleDownloadPdf() {
    setPdfLoading(true);

    try {
      await downloadReportPdf();
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "PDF download failed.";

      onError?.(message);
    } finally {
      setPdfLoading(false);
    }
  }

  if (!report) {
    return (
      <div className="app">
        <p className="error">Invalid report data.</p>

        <button
          className="secondary"
          onClick={onBack}
        >
          ← Back
        </button>
      </div>
    );
  }

  return (
    <div className="app">

      <div className="header">
        <h1>SpendLens — Analysis</h1>
        <p>{report.month_label || "Current Report"}</p>
      </div>

      <div className="kpis">

        <div className="kpi inc">
          <div className="lbl">Total Income</div>
          <div className="val">
            {fmt(summary.total_income)}
          </div>
        </div>

        <div className="kpi exp">
          <div className="lbl">Expenses</div>
          <div className="val">
            {fmt(summary.total_expenses)}
          </div>
        </div>

        <div className="kpi sav">
          <div className="lbl">Net Savings</div>
          <div className="val">
            {fmt(summary.net_savings)}
          </div>
        </div>

        <div className="kpi">
          <div className="lbl">Savings Score</div>

          <div className="val">
            {score.score || 0}/100
          </div>

          <span
            className="badge"
            style={{
              background: `${score.colour || "#22c55e"}33`,
              color: score.colour || "#22c55e",
            }}
          >
            {score.label || "Good"}
          </span>
        </div>

      </div>

      <div className="charts">

        <div className="panel">

          <h2>Category Breakdown</h2>

          <div
            className="chart-wrap"
            style={{ height: 350 }}
          >
            <Doughnut data={donutData} />
          </div>

        </div>

        <div className="panel">

          <h2>Daily Spend Trend</h2>

          <div
            className="chart-wrap"
            style={{ height: 350 }}
          >
            <Line
              data={lineData}
              options={chartOptions}
            />
          </div>

        </div>

      </div>

      <div className="panel">

        <h2>⚠ Anomaly Alerts</h2>

        {(report.anomalies || []).length ? (
          report.anomalies.map((a, i) => (
            <div key={i} className="row-item">
              {a.message}
            </div>
          ))
        ) : (
          <p>No anomalies detected.</p>
        )}

      </div>

      <div className="panel">

        <h2>💡 AI Insights</h2>

        {(report.ai_insights || []).map((item, i) => (
          <div key={i} className="row-item">
            {item}
          </div>
        ))}

      </div>

      <div className="rebal">
        <strong>Rebalancing:</strong>{" "}
        {report.rebalancing_recommendation}
      </div>

      <div className="actions">

        <button
          className="primary"
          disabled={pdfLoading}
          onClick={handleDownloadPdf}
        >
          {pdfLoading
            ? "Preparing PDF..."
            : "Download Report (PDF)"}
        </button>

        <button
          className="secondary"
          onClick={onBack}
        >
          ← Upload Another
        </button>

      </div>

      {pdfLoading && (
        <div style={{ marginTop: 20 }}>
          <SkeletonLoader lines={4} />
        </div>
      )}

    </div>
  );
}

export default ResultsPage;
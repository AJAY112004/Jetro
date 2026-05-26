import React, { Suspense, lazy, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ThemeToggle } from "./components/ThemeToggle.jsx";
import { ErrorBoundary } from "./components/ErrorBoundary.jsx";
import { UploadPage } from "./pages/UploadPage.jsx";
import { healthCheck, apiUnreachableMessage, ApiError } from "./api.js";

const ResultsPage = lazy(() => import("./pages/ResultsPage.jsx"));

function RequireReport({ report, children }) {
  if (!report) return <Navigate to="/" replace />;
  return children;
}

function AppRoutes({ report, error, apiDown, setError, setReport, handleBack }) {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (report && location.pathname === "/") {
      navigate("/results", { replace: true });
    }
  }, [report, location.pathname, navigate]);

  return (
    <Suspense
      fallback={
        <div className="app">
          <div className="panel">
            <div className="skeleton-line" />
          </div>
        </div>
      }
    >
      <Routes>
        <Route
          path="/"
          element={
            <UploadPage
              onReport={(r) => {
                setReport(r);
                setError(null);
              }}
              onError={setError}
            />
          }
        />
        <Route
          path="/results"
          element={
            <RequireReport report={report}>
              <ResultsPage report={report} onBack={handleBack} onError={setError} />
            </RequireReport>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  // Only used to improve dev UX: show a nice message before first upload.
  const [apiDown, setApiDown] = useState(false);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    healthCheck()
      .then(() => setApiDown(false))
      .catch((err) => {
        setApiDown(true);
        if (err instanceof ApiError && (err.status === 502 || err.status === 0)) {
          setError(apiUnreachableMessage(err.status || 502));
        }
      });
  }, []);

  const handleBack = () => {
    setReport(null);
    setError(null);
  };

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <div className="topbar">
          <div className="brand">SpendLens</div>
          <ThemeToggle />
        </div>

        {apiDown && !error ? (
          <div className="error topbar-advice">{apiUnreachableMessage(502)}</div>
        ) : null}

        {error ? <div className="error" style={{ maxWidth: 520, margin: "16px auto" }}>{error}</div> : null}

        <AppRoutes
          report={report}
          error={error}
          apiDown={apiDown}
          setError={setError}
          setReport={setReport}
          handleBack={handleBack}
        />
      </BrowserRouter>
    </ErrorBoundary>
  );
}

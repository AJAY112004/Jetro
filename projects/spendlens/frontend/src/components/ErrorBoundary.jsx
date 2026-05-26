import React from "react";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch() {
    // Intentionally no-op. In production you can wire this to your telemetry.
  }

  render() {
    const { hasError, error } = this.state;
    const { fallback } = this.props;

    if (!hasError) return this.props.children;

    if (fallback) return fallback({ error });

    return (
      <div className="app">
        <div className="error" style={{ maxWidth: 720, margin: "24px auto" }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Something went wrong.</div>
          <div style={{ color: "#fecaca" }}>
            {error?.message ? error.message : String(error)}
          </div>
        </div>
      </div>
    );
  }
}


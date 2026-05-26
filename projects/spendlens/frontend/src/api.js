/**
 * POST /api/analyse — multipart FormData with binary file (field: statement).
 * Do NOT set Content-Type manually; browser sets boundary for FormData.
 */

const API_BASE = import.meta.env.VITE_API_URL || "/api";
const DEBUG = import.meta.env.DEV;

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Vite proxy returns 502 with empty body when Flask on :5050 is not running. */
export function apiUnreachableMessage(status = 502) {
  if (status === 502 || status === 503 || status === 504) {
    return (
      "Cannot reach the SpendLens API (Flask is not running on port 5050). " +
      "In a second terminal run: cd projects/spendlens/scripts && python app.py"
    );
  }
  return null;
}

function errorForStatus(status, fallback) {
  return apiUnreachableMessage(status) || fallback;
}

async function readResponse(res) {
  const text = await res.text();
  if (DEBUG) {
    console.log("[api] response.status:", res.status);
    console.log("[api] response.text:", text.slice(0, 500));
  }
  if (!text) {
    return {
      success: false,
      error: errorForStatus(res.status, `Empty response (HTTP ${res.status})`),
    };
  }
  try {
    return JSON.parse(text);
  } catch {
    return { success: false, error: text.slice(0, 300) || "Invalid JSON from server" };
  }
}

let _jwtTokenPromise = null;
let _jwtToken = null;

async function ensureJwtToken() {
  if (_jwtToken) return _jwtToken;
  if (_jwtTokenPromise) return _jwtTokenPromise;

  _jwtTokenPromise = (async () => {
    const url = `${API_BASE}/auth/token`;
    const res = await fetch(url, { headers: { Accept: "application/json" }, credentials: "include" });
    const data = await readResponse(res);
    if (!res.ok || data.success === false) {
      throw new ApiError(data.error || "Auth token request failed", res.status, data.detail);
    }
    const token = data?.data?.token || null;
    const enabled = data?.data?.jwtEnabled === true;
    if (!enabled || !token) return null;
    _jwtToken = token;
    return token;
  })();

  _jwtToken = await _jwtTokenPromise;
  return _jwtToken;
}

export async function healthCheck() {
  const url = `${API_BASE}/health`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  const data = await readResponse(res);
  if (!res.ok || data.success === false) {
    throw new ApiError(data.error || "Health check failed", res.status, data.detail);
  }
  return data?.data || data;
}

export async function analyseStatement(file) {
  if (!(file instanceof File) && !(file instanceof Blob)) {
    throw new ApiError("Invalid file object — expected browser File from input", 0);
  }

  const formData = new FormData();
  formData.append("statement", file, file.name);

  const url = `${API_BASE}/analyse`;

  if (DEBUG) {
    console.log("[api] POST", url);
    console.log("[api] request: FormData with binary file", {
      field: "statement",
      fileName: file.name,
      fileSize: file.size,
      fileType: file.type,
    });
    for (const [k, v] of formData.entries()) {
      console.log("[api] formData entry:", k, v instanceof File ? `File(${v.name}, ${v.size}b)` : v);
    }
  }

  const token = await ensureJwtToken().catch(() => null);

  const res = await fetch(url, {
    method: "POST",
    body: formData,
    credentials: "include",
    headers: {
      Accept: "application/json",
      "X-Requested-With": "XMLHttpRequest",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  const data = await readResponse(res);

  if (DEBUG) {
    console.log("[api] POST /analyse →", res.status, data);
  }

  const failed = !res.ok || data.success === false;
  if (failed) {
    throw new ApiError(
      data.error || errorForStatus(res.status, `Analysis failed (HTTP ${res.status})`),
      res.status,
      data.detail
    );
  }

  if (!data?.data?.report) {
    throw new ApiError("Server returned success but no report object", res.status);
  }

  return data.data.report;
}

export async function loadDemoReport() {
  const url = `${API_BASE}/demo`;
  const res = await fetch(url, {
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  const data = await readResponse(res);
  if (!res.ok || data.success === false) {
    throw new ApiError(data.error || `Demo failed (${res.status})`, res.status, data.detail);
  }
  return data?.data?.report;
}

function parseFilenameFromDisposition(header) {
  if (!header) return null;
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (utf8) {
    try {
      return decodeURIComponent(utf8[1].trim());
    } catch {
      return utf8[1].trim();
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : null;
}

/**
 * Download PDF via fetch + blob — never navigates the page or iframe.
 * Works in dev (Vite proxy), production (same origin), and cross-origin (VITE_API_URL).
 */
export async function downloadReportPdf(filename = "spendlens_report.pdf") {
  const url = `${API_BASE}/download-pdf`;

  const token = await ensureJwtToken().catch(() => null);
  const res = await fetch(url, {
    method: "GET",
    credentials: "include",
    headers: {
      Accept: "application/pdf",
      "X-Requested-With": "XMLHttpRequest",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!res.ok) {
    const text = await res.text();
    let message = `PDF download failed (HTTP ${res.status})`;
    let payload = null;
    try {
      payload = JSON.parse(text);
      if (payload?.error) message = payload.error;
    } catch {
      payload = { raw: text };
      if (text) message = text.slice(0, 200);
    }
    if (DEBUG) {
      console.error("[api] GET /download-pdf failed:", res.status, payload);
    }
    throw new ApiError(message, res.status, payload?.detail);
  }

  const blob = await res.blob();
  if (!blob.size) {
    throw new ApiError("Server returned an empty PDF", res.status);
  }

  const name =
    parseFilenameFromDisposition(res.headers.get("Content-Disposition")) ||
    filename;

  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = name;
    anchor.rel = "noopener";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

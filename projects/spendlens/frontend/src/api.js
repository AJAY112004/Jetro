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

async function readResponse(res) {
  const text = await res.text();
  if (DEBUG) {
    console.log("[api] response.status:", res.status);
    console.log("[api] response.text:", text.slice(0, 500));
  }
  if (!text) {
    return { success: false, ok: false, error: `Empty response (HTTP ${res.status})` };
  }
  try {
    return JSON.parse(text);
  } catch {
    return { success: false, ok: false, error: text.slice(0, 300) || "Invalid JSON from server" };
  }
}

export async function healthCheck() {
  const url = `${API_BASE}/health`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  const data = await readResponse(res);
  if (!res.ok || data.success === false) {
    throw new ApiError(data.error || "Health check failed", res.status, data.detail);
  }
  return data;
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

  const res = await fetch(url, {
    method: "POST",
    body: formData,
    credentials: "include",
    headers: {
      Accept: "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
  });

  const data = await readResponse(res);

  if (DEBUG) {
    console.log("[api] POST /analyse →", res.status, data);
  }

  const failed = !res.ok || data.success === false || data.ok === false;
  if (failed) {
    throw new ApiError(
      data.error || `Analysis failed (HTTP ${res.status})`,
      res.status,
      data.detail
    );
  }

  if (!data.report) {
    throw new ApiError("Server returned success but no report object", res.status);
  }

  return data.report;
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
  return data.report;
}

export function pdfDownloadUrl() {
  return `${API_BASE}/download-pdf`;
}

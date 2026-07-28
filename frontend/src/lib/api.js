import axios from "axios";

const isDev = process.env.NODE_ENV === 'development' || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || (isDev ? "http://localhost:8000" : "");
export const API = BACKEND_URL.endsWith('/') ? `${BACKEND_URL}api` : `${BACKEND_URL}/api`;

console.log(`[Relayd] API Base URL: ${API} (mode: ${process.env.NODE_ENV}, host: ${window.location.hostname})`);

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export function formatApiError(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

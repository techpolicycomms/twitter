/**
 * API client for the AuditChain backend.
 * Handles authentication, token refresh, and all API calls.
 */

import axios, { AxiosInstance, AxiosError } from "axios";
import type { Audit, AuthTokens, Certificate, User } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3001";

/** Create a configured axios instance */
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: `${API_URL}/api`,
    headers: { "Content-Type": "application/json" },
  });

  // Attach the access token to every request
  client.interceptors.request.use((config) => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  // Handle 401/403 with automatic token refresh
  client.interceptors.response.use(
    (res) => res,
    async (error: AxiosError) => {
      const original = error.config as typeof error.config & { _retry?: boolean };
      if (error.response?.status === 403 && !original._retry) {
        original._retry = true;
        const refreshToken =
          typeof window !== "undefined" ? localStorage.getItem("refreshToken") : null;

        if (refreshToken) {
          try {
            const { data } = await axios.post(`${API_URL}/api/auth/refresh`, {
              refreshToken,
            });
            localStorage.setItem("accessToken", data.accessToken);
            localStorage.setItem("refreshToken", data.refreshToken);
            original.headers!.Authorization = `Bearer ${data.accessToken}`;
            return client(original);
          } catch {
            // Refresh failed — clear tokens and redirect to login
            localStorage.removeItem("accessToken");
            localStorage.removeItem("refreshToken");
            window.location.href = "/login";
          }
        }
      }
      return Promise.reject(error);
    }
  );

  return client;
};

export const api = createApiClient();

// ── Auth ─────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post<AuthTokens>("/auth/login", { email, password }).then((r) => r.data),

  register: (data: {
    email: string;
    password: string;
    orgName: string;
    industry: string;
    firstName?: string;
    lastName?: string;
  }) => api.post<AuthTokens>("/auth/register", data).then((r) => r.data),

  logout: (refreshToken: string) =>
    api.post("/auth/logout", { refreshToken }),

  me: () => api.get<User>("/auth/me").then((r) => r.data),
};

// ── Audits ───────────────────────────────────────────────────

export const auditsApi = {
  list: (params?: { status?: string; page?: number; limit?: number }) =>
    api.get<{ audits: Audit[]; total: number }>("/audits", { params }).then((r) => r.data),

  get: (id: string) => api.get<Audit>(`/audits/${id}`).then((r) => r.data),

  submit: (formData: FormData) =>
    api
      .post<Audit>("/audits", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data),

  delete: (id: string) => api.delete(`/audits/${id}`),
};

// ── Reports ──────────────────────────────────────────────────

export const reportsApi = {
  list: (params?: { page?: number; limit?: number; search?: string }) =>
    api.get<{ reports: Audit[]; total: number }>("/reports", { params }).then((r) => r.data),

  get: (auditId: string) => api.get<Audit>(`/reports/${auditId}`).then((r) => r.data),

  getPdfUrl: (auditId: string) => `${API_URL}/api/reports/${auditId}/pdf`,

  export: (auditId: string, format: "json" | "csv") =>
    `${API_URL}/api/reports/${auditId}/export?format=${format}`,
};

// ── Certificates ─────────────────────────────────────────────

export const certsApi = {
  mint: (auditId: string, ipfsHash: string) =>
    api.post<Certificate>("/certs/mint", { auditId, ipfsHash }).then((r) => r.data),

  verify: (tokenId: number) =>
    api.get<{ certificate: Certificate; onChain: unknown; isValid: boolean }>(
      `/certs/verify/${tokenId}`
    ).then((r) => r.data),

  lookup: (params: { modelHash?: string; certId?: string }) =>
    api.get<Certificate>("/certs/lookup", { params }).then((r) => r.data),

  revoke: (tokenId: number, reason: string) =>
    api.post(`/certs/revoke/${tokenId}`, { reason }).then((r) => r.data),
};

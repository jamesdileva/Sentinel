import axios from "axios";

import type { HealthResponse } from "../types";

export class ApiError extends Error {
  status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const api = axios.create({
  baseURL: "/api",
  timeout: 10_000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status ?? null;
    const detail = error.response?.data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : status === null
          ? "Cannot reach the Sentinel backend."
          : `Request failed (HTTP ${status}).`;
    return Promise.reject(new ApiError(message, status));
  },
);

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/v1/health");
  return data;
}

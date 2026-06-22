import { apiClient } from "./client";

export interface HealthResponse {
  status: string;
  services?: {
    database?: {
      healthy?: boolean;
      error?: string | null;
    };
    redis?: {
      healthy?: boolean;
      error?: string | null;
    };
    storage?: {
      healthy?: boolean;
      backend?: string;
    };
  };
  workers?: {
    note?: string;
  };
  metrics?: {
    storage_backend?: string;
  };
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>("/api/v1/health");
  return response.data;
}
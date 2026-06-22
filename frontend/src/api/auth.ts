import { apiClient } from "./client";
import { CurrentUser, LoginResponse } from "../types/auth";

export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>("/api/v1/auth/login", {
    email,
    password,
  });

  return response.data;
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  const response = await apiClient.get<CurrentUser>("/api/v1/auth/me");
  return response.data;
}

export async function refreshAccessToken(
  refreshToken: string
): Promise<{ access_token: string }> {
  const response = await apiClient.post<{ access_token: string }>(
    "/api/v1/auth/refresh",
    {},
    {
      headers: {
        Authorization: `Bearer ${refreshToken}`,
      },
    }
  );

  return response.data;
}
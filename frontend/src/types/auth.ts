//types/auth.ts 
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  role: "admin" | "operator" | "client" | string;
  email: string;
}

export interface CurrentUser {
  id: number;
  email: string;
  role: "admin" | "operator" | "client" | string;
  is_active: boolean;
}
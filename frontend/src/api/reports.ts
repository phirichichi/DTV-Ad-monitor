// reports.ts
import { apiClient } from "./client";

export interface ReportItem {
  detection_id: number;

  date: string | null;

  advertiser: string;
  ad_name: string;

  start_time: string | null;
  end_time: string | null;

  duration: number | null;

  channel_name: string | null;

  status: string;
  confidence_score: number | null;
  match_source: string | null;
  review_status: string | null;
  notes: string | null;

  screenshot_path: string | null;
  screenshot_url: string | null;

  capture_status: string | null;
  interruption_time: string | null;
  interruption_reason: string | null;
}

export interface DashboardSummary {
  total_users: number;
  active_channels: number;
  healthy_channels: number;
  interrupted_channels: number;
  total_advertisers: number;
  ad_library_count: number;
  monitoring_sources: number;
  detections_today: number;
  audit_events_today: number;
  evidence_items_today: number;
}

export interface AuditLogItem {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  details: string | null;
  created_at: string | null;
  user_email: string | null;
}

export interface KPIResponse {
  total: number;
  matched: number;
  uncertain: number;
  rejected: number;
  total_duration_seconds: number;
  match_rate: number;
  uncertain_rate: number;
  rejected_rate: number;
}

export interface ReportFilters {
  start_date?: string;
  end_date?: string;
  last_24_hours?: boolean;
  channel_id?: number;
  advertiser_id?: number;
  advertisement_id?: number;
  status?: string;
  review_status?: string;
  search?: string;
}

function cleanParams(params?: ReportFilters): Record<string, string | number | boolean> {
  const cleaned: Record<string, string | number | boolean> = {};

  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      cleaned[key] = value;
    }
  });

  return cleaned;
}

export async function getReports(params?: ReportFilters): Promise<ReportItem[]> {
  const response = await apiClient.get<ReportItem[]>("/api/v1/reports/", {
    params: cleanParams(params),
  });
  return response.data;
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const response = await apiClient.get<DashboardSummary>(
    "/api/v1/reports/dashboard-summary"
  );
  return response.data;
}

export async function getAuditLogs(): Promise<AuditLogItem[]> {
  const response = await apiClient.get<AuditLogItem[]>("/api/v1/reports/audit-logs");
  return response.data;
}

export async function getKPI(): Promise<KPIResponse> {
  const response = await apiClient.get<KPIResponse>("/api/v1/reports/kpi");
  return response.data;
}

export async function downloadPDF(params?: ReportFilters): Promise<Blob> {
  const response = await apiClient.get("/api/v1/reports/export/pdf", {
    params: cleanParams(params),
    responseType: "blob",
  });
  return response.data;
}

export async function downloadExcel(params?: ReportFilters): Promise<Blob> {
  const response = await apiClient.get("/api/v1/reports/export/excel", {
    params: cleanParams(params),
    responseType: "blob",
  });
  return response.data;
}

export async function downloadCSV(params?: ReportFilters): Promise<Blob> {
  const response = await apiClient.get("/api/v1/reports/export/csv", {
    params: cleanParams(params),
    responseType: "blob",
  });
  return response.data;
}
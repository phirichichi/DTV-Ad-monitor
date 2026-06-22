import { apiClient } from "./client";

export interface DetectionEvidenceItem {
  id: number;
  file_path: string;
  file_url?: string | null;
  file_type: "screenshot" | "clip" | string;
  checksum?: string | null;
  created_at: string | null;
}

export interface DetectionChannel {
  id: number;
  name: string;
}

export interface DetectionAdvertisement {
  id: number;
  title: string;
  advertiser_name?: string | null;
}

export interface Detection {
  id: number;
  detected_at: string | null;
  confidence_score: number | null;
  status: "matched" | "uncertain" | string;
  duration_seconds?: number | null;
  match_source?: string | null;
  review_status?: "pending" | "verified" | "rejected" | string | null;
  notes?: string | null;
  channel?: DetectionChannel | null;
  advertisement?: DetectionAdvertisement | null;
  evidence_items?: DetectionEvidenceItem[];
}

export interface DetectionQueryParams {
  page?: number;
  page_size?: number;
  status?: string;
  review_status?: string;
}

export async function getDetections(
  params?: DetectionQueryParams
): Promise<Detection[]> {
  const response = await apiClient.get<Detection[]>("/api/v1/detections", {
    params,
  });
  return response.data;
}

export async function verifyDetection(
  id: number
): Promise<{ status: string; detection_id: number }> {
  const response = await apiClient.post<{ status: string; detection_id: number }>(
    `/api/v1/detections/${id}/verify`
  );
  return response.data;
}

export async function rejectDetection(
  id: number,
  reason: string
): Promise<{ status: string; detection_id: number }> {
  const response = await apiClient.post<{ status: string; detection_id: number }>(
    `/api/v1/detections/${id}/reject`,
    { reason }
  );
  return response.data;
}

export function getDetectionScreenshotPath(detection: Detection): string | null {
  const item = detection.evidence_items?.find((e) => e.file_type === "screenshot");
  return item?.file_url || item?.file_path || null;
}

export function getDetectionClipPath(detection: Detection): string | null {
  const item = detection.evidence_items?.find((e) => e.file_type === "clip");
  return item?.file_url || item?.file_path || null;
}

export function getDetectionAdvertiserName(detection: Detection): string {
  return detection.advertisement?.advertiser_name || "Unknown Advertiser";
}

export function getDetectionAdvertisementTitle(detection: Detection): string {
  return detection.advertisement?.title || "Unknown Ad";
}

export function getDetectionChannelName(detection: Detection): string {
  return detection.channel?.name || "Unknown Channel";
}
import { apiClient } from "./client";

export type AdvertisementContentType =
  | "commercial"
  | "promo"
  | "sponsorship"
  | "filler";

export interface AdvertiserRow {
  id: number;
  name: string;
  contact_email?: string | null;
  contact_phone?: string | null;
  contract_start_date?: string | null;
  contract_end_date?: string | null;
  is_active: boolean;
  is_archived: boolean;
}

export interface AdvertisementRow {
  id: number;
  advertiser_id: number;
  advertiser_name: string;
  title: string;
  duration_seconds: number;
  content_type: AdvertisementContentType;
  reference_audio_signature?: string | null;
  reference_frame_hash?: string | null;
  uploaded_file_name?: string | null;
  uploaded_file_path?: string | null;
  uploaded_mime_type?: string | null;
  uploaded_file_size_bytes?: number | null;
  is_active: boolean;
}

export interface CreateAdvertiserPayload {
  name: string;
  contact_email?: string | null;
  contact_phone?: string | null;
  contract_start_date?: string | null;
  contract_end_date?: string | null;
  is_active?: boolean;
}

export interface UploadAdvertisementPayload {
  advertiser_id: number;
  title: string;
  content_type: AdvertisementContentType;
  is_active?: boolean;
  video_file: File;
}

export async function getAdvertisers(): Promise<AdvertiserRow[]> {
  const response = await apiClient.get<AdvertiserRow[]>("/api/v1/advertisers");
  return response.data;
}

export async function createAdvertiser(
  payload: CreateAdvertiserPayload
): Promise<AdvertiserRow> {
  const response = await apiClient.post<AdvertiserRow>(
    "/api/v1/advertisers",
    payload
  );
  return response.data;
}

export async function archiveAdvertiser(advertiserId: number): Promise<void> {
  await apiClient.delete(`/api/v1/advertisers/${advertiserId}`);
}

export async function getAdvertisements(): Promise<AdvertisementRow[]> {
  const response = await apiClient.get<AdvertisementRow[]>("/api/v1/advertisements");
  return response.data;
}

export async function uploadAdvertisementVideo(
  payload: UploadAdvertisementPayload
): Promise<AdvertisementRow> {
  const formData = new FormData();

  formData.append("advertiser_id", String(payload.advertiser_id));
  formData.append("title", payload.title);
  formData.append("content_type", payload.content_type);
  formData.append("is_active", String(payload.is_active ?? true));
  formData.append("video_file", payload.video_file);

  const response = await apiClient.post<AdvertisementRow>(
    "/api/v1/advertisements/upload",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );

  return response.data;
}

export async function updateAdvertisementStatus(
  advertisementId: number,
  isActive: boolean
): Promise<AdvertisementRow> {
  const response = await apiClient.patch<AdvertisementRow>(
    `/api/v1/advertisements/${advertisementId}/status`,
    { is_active: isActive }
  );

  return response.data;
}
import { apiClient } from "./client";

export interface Channel {
  id: number;
  name: string;

  input_identifier: string | null;

  capture_card_name: string | null;

  /**
   * Actual device name detected from the OS/capture subsystem.
   * Example: "USB Video Device", "Elgato HD60 X"
   */
  device_name: string | null;

  is_active: boolean;
  monitoring_enabled: boolean;
  main_channel_flag: boolean;

  capture_status: string | null;

  last_heartbeat_at: string | null;
  last_interruption_at: string | null;
  last_interruption_reason: string | null;
}

export interface CreateChannelPayload {
  name: string;
  input_identifier: string;

  capture_card_name?: string;

  is_active?: boolean;
  monitoring_enabled?: boolean;
  main_channel_flag?: boolean;
}

export interface UpdateChannelPayload {
  name?: string;
  input_identifier?: string;

  capture_card_name?: string;

  is_active?: boolean;
  monitoring_enabled?: boolean;
  main_channel_flag?: boolean;

  capture_status?: string;

  last_heartbeat_at?: string;
  last_interruption_at?: string;
  last_interruption_reason?: string;
}

export interface HeartbeatPayload {
  capture_status: string;
}

export interface ChannelProbeResponse {
  channel_id: number;
  channel_name: string;

  opened: boolean;
  frame_captured: boolean;

  width: number | null;
  height: number | null;
  fps: number | null;

  message: string;
}

export interface CaptureDeviceProbe {
  input_identifier: string;

  device_name: string | null;

  opened: boolean;
  frame_captured: boolean;

  width: number | null;
  height: number | null;
  fps: number | null;

  message: string;
}

export async function getChannels(): Promise<Channel[]> {
  const response = await apiClient.get<Channel[]>(
    "/api/v1/channels/"
  );

  return response.data;
}

export async function getMonitoringEnabledChannels(): Promise<Channel[]> {
  const response = await apiClient.get<Channel[]>(
    "/api/v1/channels/monitoring-enabled"
  );

  return response.data;
}

export async function createChannel(
  payload: CreateChannelPayload
): Promise<Channel> {
  const response = await apiClient.post<Channel>(
    "/api/v1/channels/",
    payload
  );

  return response.data;
}

export async function updateChannel(
  channelId: number,
  payload: UpdateChannelPayload
): Promise<Channel> {
  const response = await apiClient.patch<Channel>(
    `/api/v1/channels/${channelId}`,
    payload
  );

  return response.data;
}

export async function heartbeatChannel(
  channelId: number,
  captureStatus: string = "healthy"
): Promise<Channel> {
  const payload: HeartbeatPayload = {
    capture_status: captureStatus,
  };

  const response = await apiClient.post<Channel>(
    `/api/v1/channels/${channelId}/heartbeat`,
    payload
  );

  return response.data;
}

export async function probeChannel(
  channelId: number
): Promise<ChannelProbeResponse> {
  const response = await apiClient.post<ChannelProbeResponse>(
    `/api/v1/channels/${channelId}/probe`
  );

  return response.data;
}

export async function scanCaptureDevices(): Promise<CaptureDeviceProbe[]> {
  const response = await apiClient.get<CaptureDeviceProbe[]>(
    "/api/v1/channels/capture-devices"
  );

  return response.data;
}

export async function getChannelSnapshotBlobUrl(
  channelId: number
): Promise<string> {
  const response = await apiClient.get<Blob>(
    `/api/v1/channels/${channelId}/snapshot`,
    {
      params: {
        ts: Date.now(),
      },
      responseType: "blob",
    }
  );

  return URL.createObjectURL(response.data);
}

export function revokeSnapshotUrl(url?: string | null): void {
  if (url) {
    URL.revokeObjectURL(url);
  }
}
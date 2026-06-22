import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import {
  Channel,
  getChannels,
  getChannelSnapshotBlobUrl,
} from "../api/channels";
import {
  Detection,
  getDetectionAdvertisementTitle,
  getDetectionChannelName,
  getDetectionClipPath,
  getDetectionScreenshotPath,
  getDetections,
} from "../api/detections";
import { AppLayout } from "../components/layout/AppLayout";

const POLL_INTERVAL_MS = 5000;

const MonitoringPage: React.FC = () => {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [selectedDetection, setSelectedDetection] = useState<Detection | null>(null);
  const [previewChannelId, setPreviewChannelId] = useState<number | null>(null);
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadData = useCallback(async (background = false) => {
    try {
      background ? setRefreshing(true) : setLoading(true);
      setError("");

      const [channelData, detectionData] = await Promise.all([
        getChannels(),
        getDetections({ page: 1, page_size: 50 }),
      ]);

      setChannels(channelData);
      setDetections(detectionData);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load monitoring data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData(false);
    const interval = window.setInterval(() => loadData(true), POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [loadData]);

  useEffect(() => {
    return () => {
      if (snapshotUrl) {
        URL.revokeObjectURL(snapshotUrl);
      }
    };
  }, [snapshotUrl]);

  const loadSnapshot = async (channelId: number) => {
    setSnapshotLoading(true);
    setError("");

    try {
      if (snapshotUrl) {
        URL.revokeObjectURL(snapshotUrl);
      }

      const url = await getChannelSnapshotBlobUrl(channelId);
      setSnapshotUrl(url);
    } catch (err: any) {
      setSnapshotUrl(null);
      setError(err?.response?.data?.detail || "Failed to load HDMI snapshot");
    } finally {
      setSnapshotLoading(false);
    }
  };

  const togglePreview = async (channelId: number) => {
    if (previewChannelId === channelId) {
      setPreviewChannelId(null);

      if (snapshotUrl) {
        URL.revokeObjectURL(snapshotUrl);
      }

      setSnapshotUrl(null);
      return;
    }

    setPreviewChannelId(channelId);
    await loadSnapshot(channelId);
  };

  const pendingCount = useMemo(
    () => detections.filter((d) => d.review_status === "pending").length,
    [detections]
  );

  const matchedCount = useMemo(
    () => detections.filter((d) => d.status === "matched").length,
    [detections]
  );

  const interruptedCount = useMemo(
    () =>
      channels.filter((channel) =>
        ["interrupted", "disconnected", "error", "probe_failed"].includes(
          channel.capture_status || ""
        )
      ).length,
    [channels]
  );

  const channelStatusChip = (channel: Channel) => {
    if (!channel.monitoring_enabled) {
      return <Chip label="Disabled" color="default" size="small" />;
    }

    if (channel.capture_status === "healthy") {
      return <Chip label="Healthy" color="success" size="small" />;
    }

    if (
      channel.capture_status === "interrupted" ||
      channel.capture_status === "disconnected" ||
      channel.capture_status === "error"
    ) {
      return <Chip label={channel.capture_status} color="error" size="small" />;
    }

    if (channel.capture_status === "probe_failed") {
      return <Chip label="Probe Failed" color="warning" size="small" />;
    }

    return (
      <Chip
        label={channel.capture_status ?? "Unknown"}
        color="default"
        size="small"
      />
    );
  };

  const detectionStatusChip = (status?: string | null) => {
    if (status === "matched") {
      return <Chip label="matched" color="success" size="small" />;
    }

    if (status === "uncertain") {
      return <Chip label="uncertain" color="warning" size="small" />;
    }

    return <Chip label={status ?? "unknown"} size="small" />;
  };

  const reviewChip = (reviewStatus?: string | null) => {
    if (reviewStatus === "verified") {
      return <Chip label="Verified" color="success" size="small" />;
    }

    if (reviewStatus === "rejected") {
      return <Chip label="Rejected" color="error" size="small" />;
    }

    if (reviewStatus === "pending") {
      return <Chip label="Pending Review" color="warning" size="small" />;
    }

    return <Chip label={reviewStatus ?? "N/A"} size="small" />;
  };

  return (
    <AppLayout title="HDMI Monitoring">
      <Typography variant="h4" gutterBottom>
        HDMI Monitoring
      </Typography>

      <Typography sx={{ mb: 3 }}>
        Live HDMI monitoring, recent ad detections, proof screenshots, and capture interruption status.
      </Typography>

      <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: "wrap" }}>
        <Chip label={`HDMI Inputs: ${channels.length}`} />
        <Chip label={`Matched Ads: ${matchedCount}`} color="success" />
        <Chip label={`Pending Reviews: ${pendingCount}`} color="warning" />
        <Chip
          label={`Interrupted Inputs: ${interruptedCount}`}
          color={interruptedCount > 0 ? "error" : "default"}
        />
        {refreshing && <Chip label="Refreshing…" color="info" />}
      </Stack>

      {loading && <CircularProgress />}
      {error && <Alert severity="error">{error}</Alert>}

      {!loading && !error && (
        <>
          <Typography variant="h6" gutterBottom>
            HDMI Inputs
          </Typography>

          <List sx={{ mb: 3 }}>
            {channels.map((channel) => (
              <ListItem
                key={channel.id}
                divider
                alignItems="flex-start"
                secondaryAction={
                  <Stack spacing={1} alignItems="flex-end">
                    {channelStatusChip(channel)}

                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => togglePreview(channel.id)}
                    >
                      {previewChannelId === channel.id ? "Hide Preview" : "Preview"}
                    </Button>

                    {previewChannelId === channel.id && (
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => loadSnapshot(channel.id)}
                        disabled={snapshotLoading}
                      >
                        Refresh
                      </Button>
                    )}
                  </Stack>
                }
              >
                <ListItemText
                  primary={channel.name}
                  secondary={
                    <>
                      <div>HDMI Device Index: {channel.input_identifier ?? "N/A"}</div>
                      <div>Capture Card: {channel.capture_card_name ?? "N/A"}</div>
                      <div>
                        Monitoring: {channel.monitoring_enabled ? "Enabled" : "Disabled"} |
                        Last Heartbeat: {channel.last_heartbeat_at ?? "N/A"}
                      </div>
                      <div>Last Interruption: {channel.last_interruption_at ?? "N/A"}</div>
                      <div>
                        Interruption Reason: {channel.last_interruption_reason ?? "N/A"}
                      </div>

                      {previewChannelId === channel.id && (
                        <Box sx={{ mt: 2 }}>
                          <Typography variant="subtitle2" gutterBottom>
                            Current HDMI Snapshot
                          </Typography>

                          {snapshotLoading && <CircularProgress size={24} />}

                          {!snapshotLoading && snapshotUrl && (
                            <Box
                              component="img"
                              src={snapshotUrl}
                              alt={`HDMI preview for ${channel.name}`}
                              sx={{
                                width: "100%",
                                maxWidth: 620,
                                maxHeight: 360,
                                objectFit: "contain",
                                borderRadius: 1,
                                border: "1px solid #ddd",
                              }}
                            />
                          )}
                        </Box>
                      )}
                    </>
                  }
                />
              </ListItem>
            ))}

            {channels.length === 0 && (
              <ListItem>
                <ListItemText primary="No HDMI inputs configured yet." />
              </ListItem>
            )}
          </List>

          <Divider sx={{ my: 2 }} />

          <Typography variant="h6" gutterBottom>
            Recent Detected Ads
          </Typography>

          <List>
            {detections.map((detection) => (
              <ListItem
                key={detection.id}
                divider
                alignItems="flex-start"
                secondaryAction={
                  <Stack direction="column" spacing={1} alignItems="flex-end">
                    {detectionStatusChip(detection.status)}
                    {reviewChip(detection.review_status)}
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() => setSelectedDetection(detection)}
                    >
                      View Evidence
                    </Button>
                  </Stack>
                }
              >
                <ListItemText
                  primary={`${getDetectionAdvertisementTitle(detection)} | ${getDetectionChannelName(detection)}`}
                  secondary={
                    <>
                      <div>Date/Time Played: {detection.detected_at ?? "N/A"}</div>
                      <div>Duration Detected: {detection.duration_seconds ?? "N/A"}s</div>
                      <div>Confidence: {detection.confidence_score ?? "N/A"}</div>
                      <div>Match Source: {detection.match_source ?? "N/A"}</div>
                      <div>Notes: {detection.notes ?? "N/A"}</div>
                    </>
                  }
                />
              </ListItem>
            ))}

            {detections.length === 0 && (
              <ListItem>
                <ListItemText primary="No detected ads recorded yet." />
              </ListItem>
            )}
          </List>
        </>
      )}

      <Dialog
        open={Boolean(selectedDetection)}
        onClose={() => setSelectedDetection(null)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>Detection Evidence</DialogTitle>

        <DialogContent dividers>
          {!selectedDetection && <Typography>No detection selected.</Typography>}

          {selectedDetection && (
            <Box sx={{ display: "grid", gap: 2 }}>
              <Typography variant="subtitle1">
                {getDetectionAdvertisementTitle(selectedDetection)} |{" "}
                {getDetectionChannelName(selectedDetection)}
              </Typography>

              <Typography variant="body2">
                Status: {selectedDetection.status ?? "N/A"} | Review:{" "}
                {selectedDetection.review_status ?? "N/A"}
              </Typography>

              {getDetectionScreenshotPath(selectedDetection) ? (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Screenshot Proof
                  </Typography>
                  <Box
                    component="img"
                    src={getDetectionScreenshotPath(selectedDetection) ?? undefined}
                    alt="Detection screenshot"
                    sx={{
                      width: "100%",
                      maxHeight: 360,
                      objectFit: "contain",
                      borderRadius: 1,
                      border: "1px solid #ddd",
                    }}
                  />
                </Box>
              ) : (
                <Typography variant="body2">No screenshot evidence available.</Typography>
              )}

              {getDetectionClipPath(selectedDetection) ? (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Clip
                  </Typography>
                  <Box
                    component="video"
                    controls
                    src={getDetectionClipPath(selectedDetection) ?? undefined}
                    sx={{ width: "100%", borderRadius: 1 }}
                  />
                </Box>
              ) : (
                <Typography variant="body2">
                  No clip evidence available. HDMI clip buffering is not enabled yet.
                </Typography>
              )}
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
};

export default MonitoringPage;
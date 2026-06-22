//frontend/src/pages/ChannelsPage.tsx
import React, { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import { AppLayout } from "../components/layout/AppLayout";
import {
  CaptureDeviceProbe,
  Channel,
  createChannel,
  getChannels,
  getChannelSnapshotBlobUrl,
  heartbeatChannel,
  probeChannel,
  revokeSnapshotUrl,
  scanCaptureDevices,
  updateChannel,
} from "../api/channels";


const ChannelsPage: React.FC = () => {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [devices, setDevices] = useState<CaptureDeviceProbe[]>([]);

  const [name, setName] = useState("");
  const [inputIdentifier, setInputIdentifier] = useState("0");
  const [captureCardName, setCaptureCardName] = useState("");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [probingChannelId, setProbingChannelId] = useState<number | null>(null);
  const [previewChannelId, setPreviewChannelId] = useState<number | null>(null);
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);

  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const loadChannels = async () => {
    try {
      setError("");
      const data = await getChannels();
      setChannels(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load channels");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadChannels();
  }, []);

  useEffect(() => {
    return () => {
      revokeSnapshotUrl(snapshotUrl);
    };
  }, [snapshotUrl]);

  const loadSnapshot = async (channelId: number) => {
    setSnapshotLoading(true);
    setError("");

    try {
      revokeSnapshotUrl(snapshotUrl);

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

      revokeSnapshotUrl(snapshotUrl);

      setSnapshotUrl(null);
      return;
    }

    setPreviewChannelId(channelId);
    await loadSnapshot(channelId);
  };

  const validateForm = () => {
    if (!name.trim()) {
      return "Channel name is required.";
    }

    if (!inputIdentifier.trim()) {
      return "HDMI input identifier is required. Use a capture device index like 0, 1, or 2.";
    }

    return "";
  };

  const handleScanDevices = async () => {
    setError("");
    setInfo("");
    setScanning(true);

    try {
      const result = await scanCaptureDevices();
      setDevices(result);

      const openedDevices = result.filter(
        (device) => device.opened && device.frame_captured
      );

      if (openedDevices.length > 0) {
        setInputIdentifier(openedDevices[0].input_identifier);
        
        if (openedDevices[0].device_name) {
          setCaptureCardName(openedDevices[0].device_name);
        }

        setInfo(
          `Found ${openedDevices.length} usable capture device(s). Selected ${
            openedDevices[0].device_name ??
            `Device ${openedDevices[0].input_identifier}`
          }.`
        );
      } else {
        setInfo("No usable HDMI capture devices found. Try reconnecting the capture card.");
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to scan capture devices");
    } finally {
      setScanning(false);
    }
  };

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setInfo("");

    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);

    try {
      await createChannel({
        name: name.trim(),
        input_identifier: inputIdentifier.trim(),
        capture_card_name: captureCardName.trim() || undefined,
        is_active: true,
        monitoring_enabled: true,
      });

      setName("");
      setInputIdentifier("0");
      setCaptureCardName("");
      setInfo("HDMI channel created successfully.");
      await loadChannels();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to create HDMI channel");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleMonitoring = async (channel: Channel) => {
    setError("");
    setInfo("");

    try {
      await updateChannel(channel.id, {
        monitoring_enabled: !channel.monitoring_enabled,
      });
      await loadChannels();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to update channel");
    }
  };

  const handleHeartbeat = async (channel: Channel) => {
    setError("");
    setInfo("");

    try {
      await heartbeatChannel(channel.id, "healthy");
      setInfo(`Heartbeat sent for ${channel.name}.`);
      await loadChannels();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to send heartbeat");
    }
  };

  const handleProbe = async (channel: Channel) => {
    setError("");
    setInfo("");
    setProbingChannelId(channel.id);

    try {
      const result = await probeChannel(channel.id);
      setInfo(
        `${result.channel_name}: ${result.message}` +
          (result.opened
            ? ` | frame=${result.frame_captured} width=${result.width ?? "N/A"} height=${
                result.height ?? "N/A"
              } fps=${result.fps ?? "N/A"}`
            : "")
      );
      await loadChannels();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to test HDMI input");
    } finally {
      setProbingChannelId(null);
    }
  };

  return (
    <AppLayout title="HDMI Inputs">
      <Typography variant="h4" gutterBottom>
        HDMI Inputs
      </Typography>

      <Typography sx={{ mb: 2 }}>
        Configure HDMI capture-card inputs. This system no longer uses RTMP, HLS,
        VLC, file replay, or stream URLs.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {info && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {info}
        </Alert>
      )}

      <Box
        component="form"
        onSubmit={handleCreate}
        sx={{ mb: 4, display: "grid", gap: 2, maxWidth: 650 }}
      >
        <TextField
          label="Channel / HDMI Input Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />

        <Stack direction="row" spacing={1}>
          <TextField
            fullWidth
            select={devices.length > 0}
            label="HDMI Capture Device"
            value={inputIdentifier}
            onChange={(e) => {
              const selectedId = e.target.value;
              setInputIdentifier(selectedId);

              const selectedDevice = devices.find(
                (device) => device.input_identifier === selectedId
              );

              if (
                selectedDevice?.device_name &&
                !captureCardName.trim()
              ) {
                setCaptureCardName(selectedDevice.device_name);
              }
            }}
            helperText="Select the physical HDMI capture device discovered on this machine."
            required
          >
            {devices.map((device) => (
              <MenuItem
                key={device.input_identifier}
                value={device.input_identifier}
              >
                {device.device_name
                  ? `${device.device_name} (${device.input_identifier})`
                  : `Device ${device.input_identifier}`}
              </MenuItem>
            ))}
          </TextField>

          <Button variant="outlined" onClick={handleScanDevices} disabled={scanning}>
            {scanning ? "Scanning..." : "Scan Devices"}
          </Button>
        </Stack>

        <TextField
          label="Capture Card Name"
          value={captureCardName}
          onChange={(e) => setCaptureCardName(e.target.value)}
          helperText="Optional friendly name, for example: UGREEN HDMI Capture or OBS Virtual Camera."
        />

        <Button type="submit" variant="contained" disabled={saving}>
          {saving ? "Saving..." : "Save HDMI Input"}
        </Button>
      </Box>

      {loading ? (
        <CircularProgress />
      ) : (
        <List>
          {channels.map((channel) => (
            <ListItem
              key={channel.id}
              divider
              alignItems="flex-start"
              secondaryAction={
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2">Monitoring</Typography>

                  <Switch
                    checked={Boolean(channel.monitoring_enabled)}
                    onChange={() => handleToggleMonitoring(channel)}
                  />

                  <Button size="small" variant="outlined" onClick={() => handleHeartbeat(channel)}>
                    Heartbeat
                  </Button>

                  <Button
                    size="small"
                    variant="contained"
                    onClick={() => handleProbe(channel)}
                    disabled={probingChannelId === channel.id}
                  >
                    {probingChannelId === channel.id ? "Testing..." : "Test Input"}
                  </Button>

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
                    <div>
                      HDMI Input: {channel.input_identifier || "N/A"}
                    </div>

                    <div>
                      Friendly Name: {channel.capture_card_name || "Not Set"}
                    </div>

                    <div>
                      Physical Device: {channel.device_name || "Unknown"}
                    </div>

                    <div>
                      Monitoring: {channel.monitoring_enabled ? "On" : "Off"}
                    </div>

                    <div>
                      Active: {channel.is_active ? "Yes" : "No"}
                    </div>

                    <div>
                      Status:{" "}
                      <strong>
                        {channel.capture_status || "Unknown"}
                      </strong>
                    </div>

                    <div>
                      Last Heartbeat:{" "}
                      {channel.last_heartbeat_at
                        ? new Date(channel.last_heartbeat_at).toLocaleString()
                        : "N/A"}
                    </div>

                    <div>
                      Last Interruption:{" "}
                      {channel.last_interruption_at
                        ? new Date(channel.last_interruption_at).toLocaleString()
                        : "N/A"}
                    </div>

                    <div>
                      Interruption Reason:{" "}
                      {channel.last_interruption_reason || "N/A"}
                    </div>

                    {previewChannelId === channel.id && (
                      <Box sx={{ mt: 2 }}>
                        <Typography variant="subtitle2" gutterBottom>
                          HDMI Preview Snapshot
                        </Typography>

                        {snapshotLoading && <CircularProgress size={24} />}

                        {!snapshotLoading && snapshotUrl && (
                          <Box
                            component="img"
                            src={snapshotUrl}
                            alt={`Preview for ${channel.name}`}
                            sx={{
                              width: "100%",
                              maxWidth: 520,
                              maxHeight: 300,
                              objectFit: "contain",
                              border: "1px solid #ddd",
                              borderRadius: 1,
                            }}
                          />
                        )}

                        {!snapshotLoading && !snapshotUrl && (
                          <Typography variant="body2" color="text.secondary">
                            No preview available.
                          </Typography>
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
      )}
    </AppLayout>
  );
};


export default ChannelsPage;
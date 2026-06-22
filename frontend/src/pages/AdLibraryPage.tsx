import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
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
  AdvertisementContentType,
  AdvertisementRow,
  AdvertiserRow,
  archiveAdvertiser,
  createAdvertiser,
  getAdvertisements,
  getAdvertisers,
  updateAdvertisementStatus,
  uploadAdvertisementVideo,
} from "../api/advertisements";

const MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024;

const AdLibraryPage: React.FC = () => {
  const [advertisers, setAdvertisers] = useState<AdvertiserRow[]>([]);
  const [ads, setAds] = useState<AdvertisementRow[]>([]);

  const [advertiserName, setAdvertiserName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contractStartDate, setContractStartDate] = useState("");
  const [contractEndDate, setContractEndDate] = useState("");

  const [advertiserId, setAdvertiserId] = useState("");
  const [title, setTitle] = useState("");
  const [contentType, setContentType] =
    useState<AdvertisementContentType>("commercial");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedFileName, setSelectedFileName] = useState("");

  const [loading, setLoading] = useState(true);
  const [creatingAdvertiser, setCreatingAdvertiser] = useState(false);
  const [uploadingAd, setUploadingAd] = useState(false);
  const [actionId, setActionId] = useState<number | null>(null);

  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const loadData = async () => {
    try {
      setError("");

      const [advertiserRows, adRows] = await Promise.all([
        getAdvertisers(),
        getAdvertisements(),
      ]);

      setAdvertisers(advertiserRows);
      setAds(adRows);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load ad library");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const adsByAdvertiser = useMemo(() => {
    const grouped = new Map<number, AdvertisementRow[]>();

    ads.forEach((ad) => {
      const current = grouped.get(ad.advertiser_id) || [];
      current.push(ad);
      grouped.set(ad.advertiser_id, current);
    });

    return grouped;
  }, [ads]);

  const resetAdvertiserForm = () => {
    setAdvertiserName("");
    setContactEmail("");
    setContactPhone("");
    setContractStartDate("");
    setContractEndDate("");
  };

  const resetAdForm = () => {
    setAdvertiserId("");
    setTitle("");
    setContentType("commercial");
    setSelectedFile(null);
    setSelectedFileName("");
  };

  const validateAdvertiserForm = (): string => {
    if (!advertiserName.trim()) {
      return "Advertiser name is required.";
    }

    if (contractStartDate && contractEndDate) {
      const start = new Date(`${contractStartDate}T00:00:00`);
      const end = new Date(`${contractEndDate}T00:00:00`);

      if (end < start) {
        return "Contract end date cannot be before contract start date.";
      }
    }

    return "";
  };

  const validateAdForm = (): string => {
    if (!advertiserId) {
      return "Please select an advertiser.";
    }

    if (!title.trim()) {
      return "Please enter an advertisement title.";
    }

    if (!selectedFile) {
      return "Please select a video file.";
    }

    if (!selectedFile.type.startsWith("video/")) {
      return "Please select a valid video file.";
    }

    if (selectedFile.size <= 0) {
      return "The selected video file is empty.";
    }

    if (selectedFile.size > MAX_FILE_SIZE_BYTES) {
      return "The selected video file is larger than 500MB.";
    }

    return "";
  };

  const handleCreateAdvertiser = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setInfo("");

    const validationError = validateAdvertiserForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setCreatingAdvertiser(true);

    try {
      const created = await createAdvertiser({
        name: advertiserName.trim(),
        contact_email: contactEmail.trim() || null,
        contact_phone: contactPhone.trim() || null,
        contract_start_date: contractStartDate || null,
        contract_end_date: contractEndDate || null,
        is_active: true,
      });

      resetAdvertiserForm();
      setAdvertiserId(String(created.id));
      setInfo(`Advertiser "${created.name}" created successfully.`);
      await loadData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(
        Array.isArray(detail)
          ? detail.map((item: any) => item.msg).join(" ")
          : detail || "Failed to create advertiser"
      );
    } finally {
      setCreatingAdvertiser(false);
    }
  };

  const handleUploadAd = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setInfo("");

    const validationError = validateAdForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    if (!selectedFile) {
      setError("Please select a video file.");
      return;
    }

    setUploadingAd(true);

    try {
      const created = await uploadAdvertisementVideo({
        advertiser_id: Number(advertiserId),
        title: title.trim(),
        content_type: contentType,
        is_active: true,
        video_file: selectedFile,
      });

      setInfo(
        `Video uploaded. Duration: ${created.duration_seconds}s | Frame hash: ${
          created.reference_frame_hash ? "generated" : "missing"
        } | Audio fingerprint: ${
          created.reference_audio_signature ? "generated" : "missing"
        }`
      );

      resetAdForm();
      await loadData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(
        typeof detail === "string"
          ? detail
          : "Failed to upload advertisement video"
      );
    } finally {
      setUploadingAd(false);
    }
  };

  const handleArchiveAdvertiser = async (advertiser: AdvertiserRow) => {
    const confirmed = window.confirm(
      `Archive advertiser "${advertiser.name}"? Existing historical detections will remain.`
    );

    if (!confirmed) {
      return;
    }

    setError("");
    setInfo("");
    setActionId(advertiser.id);

    try {
      await archiveAdvertiser(advertiser.id);
      setInfo(`Advertiser "${advertiser.name}" archived successfully.`);
      await loadData();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to archive advertiser");
    } finally {
      setActionId(null);
    }
  };

  const handleToggleAd = async (ad: AdvertisementRow) => {
    setError("");
    setInfo("");
    setActionId(ad.id);

    try {
      await updateAdvertisementStatus(ad.id, !ad.is_active);
      setInfo(
        `Advertisement "${ad.title}" ${
          !ad.is_active ? "activated" : "deactivated"
        }.`
      );
      await loadData();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to update advertisement");
    } finally {
      setActionId(null);
    }
  };

  return (
    <AppLayout title="Ad Library">
      <Typography variant="h4" gutterBottom>
        Ad Library
      </Typography>

      <Typography sx={{ mb: 2 }}>
        Manage advertisers and their reference advertisement videos in one place.
        These uploaded videos are what the HDMI monitoring system matches against.
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

      <Typography variant="h6" gutterBottom>
        Create Advertiser
      </Typography>

      <Box
        component="form"
        onSubmit={handleCreateAdvertiser}
        sx={{ mb: 4, display: "grid", gap: 2, maxWidth: 650 }}
      >
        <TextField
          label="Advertiser Name"
          value={advertiserName}
          onChange={(e) => setAdvertiserName(e.target.value)}
          required
        />

        <TextField
          label="Contact Email"
          type="email"
          value={contactEmail}
          onChange={(e) => setContactEmail(e.target.value)}
        />

        <TextField
          label="Contact Phone"
          value={contactPhone}
          onChange={(e) => setContactPhone(e.target.value)}
        />

        <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
          <TextField
            fullWidth
            label="Contract Start Date"
            type="date"
            value={contractStartDate}
            onChange={(e) => setContractStartDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />

          <TextField
            fullWidth
            label="Contract End Date"
            type="date"
            value={contractEndDate}
            onChange={(e) => setContractEndDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
        </Stack>

        <Button type="submit" variant="contained" disabled={creatingAdvertiser}>
          {creatingAdvertiser ? "Creating..." : "Create Advertiser"}
        </Button>
      </Box>

      <Divider sx={{ my: 3 }} />

      <Typography variant="h6" gutterBottom>
        Upload Advertisement Video
      </Typography>

      <Box
        component="form"
        onSubmit={handleUploadAd}
        sx={{ mb: 4, display: "grid", gap: 2, maxWidth: 650 }}
      >
        <TextField
          select
          label="Advertiser"
          value={advertiserId}
          onChange={(e) => setAdvertiserId(e.target.value)}
          required
        >
          {advertisers.map((advertiser) => (
            <MenuItem key={advertiser.id} value={String(advertiser.id)}>
              {advertiser.name}
            </MenuItem>
          ))}
        </TextField>

        <TextField
          label="Ad Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />

        <TextField
          select
          label="Content Type"
          value={contentType}
          onChange={(e) =>
            setContentType(e.target.value as AdvertisementContentType)
          }
        >
          <MenuItem value="commercial">commercial</MenuItem>
          <MenuItem value="promo">promo</MenuItem>
          <MenuItem value="sponsorship">sponsorship</MenuItem>
          <MenuItem value="filler">filler</MenuItem>
        </TextField>

        <Button variant="outlined" component="label">
          Select Video File
          <input
            hidden
            type="file"
            accept="video/*"
            onChange={(e) => {
              const file = e.target.files?.[0] || null;
              setSelectedFile(file);
              setSelectedFileName(file ? file.name : "");
            }}
          />
        </Button>

        {selectedFileName && (
          <Typography variant="body2">Selected file: {selectedFileName}</Typography>
        )}

        <Button
          type="submit"
          variant="contained"
          disabled={uploadingAd || !selectedFile}
        >
          {uploadingAd ? "Processing video..." : "Upload Advertisement"}
        </Button>
      </Box>

      <Divider sx={{ my: 3 }} />

      <Typography variant="h6" gutterBottom>
        Advertisers and Videos
      </Typography>

      {loading ? (
        <CircularProgress />
      ) : advertisers.length === 0 ? (
        <Alert severity="info">No advertisers created yet.</Alert>
      ) : (
        <List>
          {advertisers.map((advertiser) => {
            const advertiserAds = adsByAdvertiser.get(advertiser.id) || [];

            return (
              <ListItem key={advertiser.id} divider alignItems="flex-start">
                <ListItemText
                  primary={advertiser.name}
                  secondary={
                    <>
                      <div>
                        Email: {advertiser.contact_email || "N/A"} | Phone:{" "}
                        {advertiser.contact_phone || "N/A"}
                      </div>
                      <div>
                        Contract: {advertiser.contract_start_date || "N/A"} to{" "}
                        {advertiser.contract_end_date || "N/A"}
                      </div>
                      <div>Videos: {advertiserAds.length}</div>

                      <Box sx={{ mt: 1 }}>
                        <Button
                          size="small"
                          color="error"
                          variant="outlined"
                          disabled={actionId === advertiser.id}
                          onClick={() => handleArchiveAdvertiser(advertiser)}
                        >
                          {actionId === advertiser.id
                            ? "Archiving..."
                            : "Archive Advertiser"}
                        </Button>
                      </Box>

                      <List dense sx={{ mt: 1 }}>
                        {advertiserAds.map((ad) => (
                          <ListItem
                            key={ad.id}
                            divider
                            secondaryAction={
                              <Stack direction="row" spacing={1} alignItems="center">
                                <Typography variant="body2">Active</Typography>
                                <Switch
                                  checked={ad.is_active}
                                  disabled={actionId === ad.id}
                                  onChange={() => handleToggleAd(ad)}
                                />
                              </Stack>
                            }
                          >
                            <ListItemText
                              primary={`${ad.title} (${ad.duration_seconds}s)`}
                              secondary={
                                <>
                                  <div>Type: {ad.content_type}</div>
                                  <div>File: {ad.uploaded_file_name || "N/A"}</div>
                                  <div>
                                    Frame Hash:{" "}
                                    {ad.reference_frame_hash
                                      ? "Generated"
                                      : "Missing"}{" "}
                                    | Audio:{" "}
                                    {ad.reference_audio_signature
                                      ? "Generated"
                                      : "Missing"}
                                  </div>
                                </>
                              }
                            />
                          </ListItem>
                        ))}

                        {advertiserAds.length === 0 && (
                          <ListItem>
                            <ListItemText primary="No videos uploaded for this advertiser yet." />
                          </ListItem>
                        )}
                      </List>
                    </>
                  }
                />
              </ListItem>
            );
          })}
        </List>
      )}
    </AppLayout>
  );
};

export default AdLibraryPage;
//frontend/src/pages/DashboardPage.tsx
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  CircularProgress,
  LinearProgress,
  Stack,
  Typography,
} from "@mui/material";
import { AppLayout } from "../components/layout/AppLayout";
import { useAuth } from "../features/auth/AuthContext";
import { getDashboardSummary, DashboardSummary } from "../api/reports";
import { getChannels } from "../api/channels";
import {
  getDetections,
  Detection,
  getDetectionAdvertiserName,
  getDetectionChannelName,
} from "../api/detections";
import { apiClient } from "../api/client";

type UserRow = {
  id: number;
  email: string;
  role?: string | null;
  is_active: boolean;
};

type AdvertiserRow = {
  id: number;
  name: string;
  is_active: boolean;
};

type AdvertisementRow = {
  id: number;
  advertiser_id: number;
  advertiser_name: string;
  title: string;
  duration_seconds: number;
  content_type: string;
  is_active: boolean;
};

type DashboardCard = {
  title: string;
  value: string;
};

const POLL_INTERVAL_MS = 5000;

const DashboardPage: React.FC = () => {
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [warning, setWarning] = useState("");

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [channels, setChannels] = useState<any[]>([]);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [advertisers, setAdvertisers] = useState<AdvertiserRow[]>([]);
  const [ads, setAds] = useState<AdvertisementRow[]>([]);

  const loadData = useCallback(async (background = false) => {
    const warnings: string[] = [];

    try {
      background ? setRefreshing(true) : setLoading(true);

      const results = await Promise.allSettled([
        getDashboardSummary(),
        apiClient.get<UserRow[]>("/api/v1/users"),
        getChannels(),
        getDetections({ page: 1, page_size: 200 }),
        apiClient.get<AdvertiserRow[]>("/api/v1/advertisers"),
        apiClient.get<AdvertisementRow[]>("/api/v1/advertisements"),
      ]);

      const [
        summaryResult,
        usersResult,
        channelsResult,
        detectionsResult,
        advertisersResult,
        adsResult,
      ] = results;

      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      } else {
        warnings.push("Dashboard summary endpoint is unavailable; showing fallback counts.");
      }

      if (usersResult.status === "fulfilled") {
        setUsers(usersResult.value.data);
      }

      if (channelsResult.status === "fulfilled") {
        setChannels(channelsResult.value);
      }

      if (detectionsResult.status === "fulfilled") {
        setDetections(detectionsResult.value);
      }

      if (advertisersResult.status === "fulfilled") {
        setAdvertisers(advertisersResult.value.data);
      }

      if (adsResult.status === "fulfilled") {
        setAds(adsResult.value.data);
      }

      setWarning(warnings.join(" "));
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

  const cards = useMemo<DashboardCard[]>(() => {
    const activeChannels = channels.filter((item) => item.is_active).length;
    const healthyChannels = channels.filter((item) => item.capture_status === "healthy").length;
    const interruptedChannels = channels.filter((item) =>
      ["interrupted", "disconnected", "error", "probe_failed"].includes(
        item.capture_status
      )
    ).length;
    const monitoringSources = channels.filter((item) => item.monitoring_enabled).length;

    const detectionsToday = detections.length;
    const totalUsers = users.length;
    const activeUsers = users.filter((item) => item.is_active).length;
    const totalAdvertisers = advertisers.length;
    const activeAdvertisers = advertisers.filter((item) => item.is_active).length;
    const adLibraryCount = ads.length;

    const matchedCount = detections.filter((item) => item.status === "matched").length;
    const uncertainCount = detections.filter((item) => item.status === "uncertain").length;
    const pendingReviews = detections.filter((item) => item.review_status === "pending").length;

    if (user?.role === "admin") {
      return [
        { title: "Total Users", value: String(summary?.total_users ?? totalUsers) },
        { title: "Active Users", value: String(activeUsers) },
        { title: "Active HDMI Inputs", value: String(summary?.active_channels ?? activeChannels) },
        { title: "Healthy Inputs", value: String(summary?.healthy_channels ?? healthyChannels) },
        { title: "Interrupted Inputs", value: String(summary?.interrupted_channels ?? interruptedChannels) },
        { title: "Monitoring Sources", value: String(summary?.monitoring_sources ?? monitoringSources) },
        { title: "Advertisers", value: String(summary?.total_advertisers ?? totalAdvertisers) },
        { title: "Active Advertisers", value: String(activeAdvertisers) },
        { title: "Ad Library", value: String(summary?.ad_library_count ?? adLibraryCount) },
        { title: "Detections Today", value: String(summary?.detections_today ?? detectionsToday) },
      ];
    }

    if (user?.role === "operator") {
      return [
        { title: "Active HDMI Inputs", value: String(activeChannels) },
        { title: "Healthy Inputs", value: String(healthyChannels) },
        { title: "Interrupted Inputs", value: String(interruptedChannels) },
        { title: "Pending Reviews", value: String(pendingReviews) },
        { title: "Matched Detections", value: String(matchedCount) },
        { title: "Uncertain Detections", value: String(uncertainCount) },
      ];
    }

    const matchRate = detectionsToday > 0 ? (matchedCount / detectionsToday) * 100 : 0;

    return [
      { title: "Campaign Ads", value: String(adLibraryCount) },
      { title: "Match Rate", value: `${Math.max(0, matchRate).toFixed(1)}%` },
      { title: "Matched Spots", value: String(matchedCount) },
      { title: "Uncertain Spots", value: String(uncertainCount) },
    ];
  }, [ads, advertisers, channels, detections, summary, user?.role, users]);

  const topAdvertisers = useMemo(() => {
    const counts = new Map<string, number>();

    detections.forEach((item) => {
      const name = getDetectionAdvertiserName(item);
      counts.set(name, (counts.get(name) || 0) + 1);
    });

    return Array.from(counts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  }, [detections]);

  const topChannels = useMemo(() => {
    const counts = new Map<string, number>();

    detections.forEach((item) => {
      const name = getDetectionChannelName(item);
      counts.set(name, (counts.get(name) || 0) + 1);
    });

    return Array.from(counts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  }, [detections]);

  const statusCounts = useMemo(() => {
    const matched = detections.filter((d) => d.status === "matched").length;
    const uncertain = detections.filter((d) => d.status === "uncertain").length;
    return { matched, uncertain };
  }, [detections]);

  const maxAdvertiser = Math.max(...topAdvertisers.map((x) => x.count), 1);
  const maxChannel = Math.max(...topChannels.map((x) => x.count), 1);
  const totalStatus = Math.max(statusCounts.matched + statusCounts.uncertain, 1);

  return (
    <AppLayout title="Dashboard">
      <Typography variant="h4" gutterBottom>
        {user?.role === "admin"
          ? "Admin Dashboard"
          : user?.role === "operator"
          ? "Operator Dashboard"
          : "Client Dashboard"}
      </Typography>

      <Typography variant="body1" sx={{ mb: 3 }}>
        Live overview of HDMI inputs, detected ads, advertisers, and evidence.
      </Typography>

      {refreshing && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Refreshing live dashboard…
        </Alert>
      )}

      {loading && <CircularProgress />}

      {!loading && warning && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {warning}
        </Alert>
      )}

      {!loading && (
        <>
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: {
                xs: "1fr",
                md: "repeat(2, 1fr)",
                lg: "repeat(4, 1fr)",
              },
              gap: 3,
              mb: 4,
            }}
          >
            {cards.map((card) => (
              <Card key={card.title}>
                <CardContent>
                  <Typography variant="subtitle2" color="text.secondary">
                    {card.title}
                  </Typography>
                  <Typography variant="h5">{card.value}</Typography>
                </CardContent>
              </Card>
            ))}
          </Box>

          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", lg: "repeat(3, 1fr)" },
              gap: 3,
            }}
          >
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Detection Status Mix
                </Typography>

                <Stack spacing={2}>
                  <Box>
                    <Typography variant="body2">
                      Matched: {statusCounts.matched}
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={(statusCounts.matched / totalStatus) * 100}
                    />
                  </Box>

                  <Box>
                    <Typography variant="body2">
                      Uncertain: {statusCounts.uncertain}
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={(statusCounts.uncertain / totalStatus) * 100}
                    />
                  </Box>
                </Stack>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Top Advertisers
                </Typography>

                <Stack spacing={2}>
                  {topAdvertisers.length === 0 && (
                    <Typography variant="body2">No advertiser activity yet.</Typography>
                  )}

                  {topAdvertisers.map((item) => (
                    <Box key={item.name}>
                      <Typography variant="body2">
                        {item.name} ({item.count})
                      </Typography>
                      <LinearProgress
                        variant="determinate"
                        value={(item.count / maxAdvertiser) * 100}
                      />
                    </Box>
                  ))}
                </Stack>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  HDMI Input Activity
                </Typography>

                <Stack spacing={2}>
                  {topChannels.length === 0 && (
                    <Typography variant="body2">No channel activity yet.</Typography>
                  )}

                  {topChannels.map((item) => (
                    <Box key={item.name}>
                      <Typography variant="body2">
                        {item.name} ({item.count})
                      </Typography>
                      <LinearProgress
                        variant="determinate"
                        value={(item.count / maxChannel) * 100}
                      />
                    </Box>
                  ))}
                </Stack>
              </CardContent>
            </Card>
          </Box>
        </>
      )}
    </AppLayout>
  );
};

export default DashboardPage;
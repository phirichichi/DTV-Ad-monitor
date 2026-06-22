//OpertionHealthpage.tsx 
import React, { useEffect, useState } from "react";
import {
  Alert,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import { AppLayout } from "../components/layout/AppLayout";
import { apiClient } from "../api/client";
import { AuditLogItem, getAuditLogs } from "../api/reports";

type HealthResponse = {
  status: string;
  services?: {
    database?: {
      healthy?: boolean;
      error?: string | null;
    };
    redis?: {
      healthy?: boolean;
    };
    storage?: {
      healthy?: boolean;
      backend?: string | null;
    };
  };
  workers?: {
    note?: string;
    ingestion?: string;
    detection?: string;
    reconciliation?: string;
    reporting?: string;
  };
  metrics?: {
    queue_lag?: number;
    detections_per_minute?: number;
    storage_backend?: string;
  };
};

const OperationsHealthPage: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [warning, setWarning] = useState("");

  useEffect(() => {
    const loadData = async () => {
      const warnings: string[] = [];

      const results = await Promise.allSettled([
        apiClient.get<HealthResponse>("/api/v1/health"),
        getAuditLogs(),
      ]);

      const [healthResult, logsResult] = results;

      if (healthResult.status === "fulfilled") {
        setHealth(healthResult.value.data);
      } else {
        warnings.push("Health endpoint unavailable.");
      }

      if (logsResult.status === "fulfilled") {
        setLogs(logsResult.value);
      } else {
        warnings.push("Audit logs endpoint unavailable.");
      }

      setWarning(warnings.join(" "));
      setLoading(false);
    };

    loadData();
  }, []);

  const databaseHealthy = health?.services?.database?.healthy;
  const redisHealthy = health?.services?.redis?.healthy;
  const storageHealthy = health?.services?.storage?.healthy;

  return (
    <AppLayout title="Operations Health">
      <Typography variant="h4" gutterBottom>
        Operations Health
      </Typography>

      {warning && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {warning}
        </Alert>
      )}

      {loading ? (
        <CircularProgress />
      ) : (
        <>
          <Typography variant="h6">System Status</Typography>

          <Stack spacing={1} sx={{ mb: 3 }}>
            <Typography>
              Overall Status: {health?.status || "Unavailable"}
            </Typography>
            <Typography>
              Database Healthy:{" "}
              {databaseHealthy === true
                ? "Yes"
                : databaseHealthy === false
                ? "No"
                : "Unknown"}
            </Typography>
            <Typography>
              Redis Healthy:{" "}
              {redisHealthy === true
                ? "Yes"
                : redisHealthy === false
                ? "No"
                : "Unknown"}
            </Typography>
            <Typography>
              Storage Healthy:{" "}
              {storageHealthy === true
                ? "Yes"
                : storageHealthy === false
                ? "No"
                : "Unknown"}
            </Typography>
            <Typography>
              Storage Backend: {health?.services?.storage?.backend || health?.metrics?.storage_backend || "N/A"}
            </Typography>
          </Stack>

          {health?.workers && (
            <>
              <Typography variant="h6" gutterBottom>
                Worker Health
              </Typography>
              <Stack spacing={1} sx={{ mb: 3 }}>
                {health.workers.note && <Typography>Workers: {health.workers.note}</Typography>}
                {health.workers.ingestion && <Typography>Ingestion: {health.workers.ingestion}</Typography>}
                {health.workers.detection && <Typography>Detection: {health.workers.detection}</Typography>}
                {health.workers.reconciliation && (
                  <Typography>Reconciliation: {health.workers.reconciliation}</Typography>
                )}
                {health.workers.reporting && <Typography>Reporting: {health.workers.reporting}</Typography>}
              </Stack>
            </>
          )}

          {health?.metrics && (
            <>
              <Typography variant="h6" gutterBottom>
                Operational Metrics
              </Typography>
              <Stack spacing={1} sx={{ mb: 3 }}>
                <Typography>
                  Queue Lag: {health.metrics.queue_lag ?? "N/A"}
                </Typography>
                <Typography>
                  Detection Throughput: {health.metrics.detections_per_minute ?? "N/A"} detections/min
                </Typography>
              </Stack>
            </>
          )}

          {health?.services?.database?.error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              Database error: {health.services.database.error}
            </Alert>
          )}

          <Typography variant="h6" gutterBottom>
            Recent Audit Activity
          </Typography>

          <List>
            {logs.map((log) => (
              <ListItem key={log.id} divider>
                <ListItemText
                  primary={`${log.action} | ${log.entity_type} ${log.entity_id ?? ""}`}
                  secondary={`User: ${log.user_email || "N/A"} | Time: ${
                    log.created_at || "N/A"
                  } | Details: ${log.details || "N/A"}`}
                />
              </ListItem>
            ))}

            {logs.length === 0 && (
              <ListItem>
                <ListItemText primary="No audit log records available from backend." />
              </ListItem>
            )}
          </List>
        </>
      )}
    </AppLayout>
  );
};

export default OperationsHealthPage;
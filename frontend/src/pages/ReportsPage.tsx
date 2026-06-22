//frontend/src/pages/ReportsPage.tsx
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { AppLayout } from "../components/layout/AppLayout";
import {
  downloadCSV,
  downloadExcel,
  downloadPDF,
  getReports,
  ReportFilters,
  ReportItem,
} from "../api/reports";

const ReportsPage: React.FC = () => {
  const [rows, setRows] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const [search, setSearch] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [detectionStatus, setDetectionStatus] = useState("");

  const [previewOpen, setPreviewOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [exportPromptOpen, setExportPromptOpen] = useState(false);
  const [selectedReport, ] = useState<ReportItem | null>(null);
  const [exportFormat, setExportFormat] = useState("csv");

  const activeFilters = useMemo<ReportFilters>(
    () => ({
      start_date: fromDate || undefined,
      end_date: toDate || undefined,
      review_status: reviewStatus || undefined,
      status: detectionStatus || undefined,
      search: search.trim() || undefined,
    }),
    [fromDate, toDate, reviewStatus, detectionStatus, search]
  );

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError("");
    setInfo("");

    try {
      const data = await getReports(activeFilters);
      setRows(data);
      
      // Debug: Show in console table
      console.table(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load report data");
    } finally {
      setLoading(false);
    }
  }, [activeFilters]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const triggerBrowserDownload = (blob: Blob, fileName: string) => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = fileName;
    link.click();

    window.URL.revokeObjectURL(url);
  };

  const handleExportAction = async () => {
    setError("");
    setInfo("");
    setExporting(true);

    try {
      if (exportFormat === "csv") {
        const blob = await downloadCSV(activeFilters);
        triggerBrowserDownload(blob, "dtv_detection_report.csv");
      } else if (exportFormat === "excel") {
        const blob = await downloadExcel(activeFilters);
        triggerBrowserDownload(blob, "dtv_detection_report.xlsx");
      } else {
        const blob = await downloadPDF(activeFilters);
        triggerBrowserDownload(blob, "dtv_detection_report.pdf");
      }

      setInfo("Report exported successfully.");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to export report");
    } finally {
      setExporting(false);
      setExportPromptOpen(false);
    }
  };

  const clearFilters = () => {
    setSearch("");
    setFromDate("");
    setToDate("");
    setReviewStatus("");
    setDetectionStatus("");
  };

  return (
    <AppLayout title="Reports">
      <Typography variant="h4" gutterBottom>
        Reports
      </Typography>

      <Typography sx={{ mb: 3 }}>
        Review detected ads, proof screenshots, HDMI capture status, and export reports.
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {info && <Alert severity="info" sx={{ mb: 2 }}>{info}</Alert>}

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "repeat(5, 1fr)" },
          gap: 2,
          mb: 2,
        }}
      >
        <TextField
          label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Advertiser, ad name, channel"
        />

        <TextField
          label="From"
          type="date"
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
          InputLabelProps={{ shrink: true }}
        />

        <TextField
          label="To"
          type="date"
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
          InputLabelProps={{ shrink: true }}
        />

        <TextField
          select
          label="Review Status"
          value={reviewStatus}
          onChange={(e) => setReviewStatus(e.target.value)}
        >
          <MenuItem value="">All</MenuItem>
          <MenuItem value="pending">Pending</MenuItem>
          <MenuItem value="verified">Verified</MenuItem>
          <MenuItem value="rejected">Rejected</MenuItem>
        </TextField>

        <TextField
          select
          label="Detection Status"
          value={detectionStatus}
          onChange={(e) => setDetectionStatus(e.target.value)}
        >
          <MenuItem value="">All</MenuItem>
          <MenuItem value="matched">Matched</MenuItem>
          <MenuItem value="uncertain">Uncertain</MenuItem>
        </TextField>
      </Box>

      <Stack direction="row" spacing={1} sx={{ mb: 3, flexWrap: "wrap" }}>
        <Button variant="outlined" onClick={loadReports}>
          Apply Filters
        </Button>
        <Button variant="outlined" onClick={clearFilters}>
          Clear
        </Button>
        <Button variant="outlined" onClick={() => setPreviewOpen(true)}>
          Preview
        </Button>
        <Button variant="contained" onClick={() => setExportPromptOpen(true)}>
          Export
        </Button>
      </Stack>

      {loading ? (
        <CircularProgress />
      ) : (
        <Box sx={{ mt: 2, overflow: "auto" }}>
          <Table
            sx={{
              border: "1px solid #ddd",
              minWidth: 600,
              "& th": {
                backgroundColor: "#f5f5f5",
                borderBottom: "2px solid #ddd",
                fontWeight: "bold",
                padding: "12px",
                textAlign: "left",
              },
              "& td": {
                padding: "10px 12px",
                borderBottom: "1px solid #eee",
              },
            }}
          >
            <TableHead>
  <TableRow>
    <TableCell>Date</TableCell>
    <TableCell>Ad Name</TableCell>
    <TableCell>Advertiser</TableCell>
    <TableCell>Start Time</TableCell>
    <TableCell>End Time</TableCell>
    <TableCell>Duration</TableCell>
  </TableRow>
</TableHead>

<TableBody>
  {rows.map((report) => (
    <TableRow key={report.detection_id}>
      <TableCell>{report.date || "N/A"}</TableCell>
      <TableCell>{report.ad_name || "N/A"}</TableCell>
      <TableCell>{report.advertiser || "N/A"}</TableCell>
      <TableCell>{report.start_time || "N/A"}</TableCell>
      <TableCell>{report.end_time || "N/A"}</TableCell>
      <TableCell>
        {report.duration != null ? `${report.duration}s` : "N/A"}
      </TableCell>
    </TableRow>
  ))}
</TableBody>
          </Table>

          {rows.length === 0 && (
            <Typography variant="body1" sx={{ p: 2, color: "text.secondary" }}>
              No report rows match the selected filters.
            </Typography>
          )}
        </Box>
      )}

      {/* Preview Dialog - Also updated with Table */}
      <Dialog open={previewOpen} onClose={() => setPreviewOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>Report Preview</DialogTitle>
        <DialogContent dividers>
          {rows.length === 0 ? (
            <Typography>No rows available for preview.</Typography>
          ) : (
            <Table>
              <TableHead>
  <TableRow sx={{ backgroundColor: "#f5f5f5" }}>
    <TableCell style={{ fontWeight: "bold" }}>Date</TableCell>
    <TableCell style={{ fontWeight: "bold" }}>Ad Name</TableCell>
    <TableCell style={{ fontWeight: "bold" }}>Advertiser</TableCell>
    <TableCell style={{ fontWeight: "bold" }}>Start Time</TableCell>
    <TableCell style={{ fontWeight: "bold" }}>End Time</TableCell>
    <TableCell style={{ fontWeight: "bold" }}>Duration</TableCell>
  </TableRow>
</TableHead>

<TableBody>
  {rows.map((report) => (
    <TableRow key={report.detection_id}>
      <TableCell>{report.date || "N/A"}</TableCell>
      <TableCell>{report.ad_name || "N/A"}</TableCell>
      <TableCell>{report.advertiser || "N/A"}</TableCell>
      <TableCell>{report.start_time || "N/A"}</TableCell>
      <TableCell>{report.end_time || "N/A"}</TableCell>
      <TableCell>
        {report.duration != null ? `${report.duration}s` : "N/A"}
      </TableCell>
    </TableRow>
  ))}
</TableBody>
            </Table>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPreviewOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Evidence Dialog (unchanged) */}
      <Dialog open={evidenceOpen} onClose={() => setEvidenceOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>Evidence Preview</DialogTitle>
        <DialogContent dividers>
          {!selectedReport && <Typography>No report row selected.</Typography>}

          {selectedReport && (
            <Box sx={{ display: "grid", gap: 2 }}>
              <Typography variant="subtitle1">
                {selectedReport.ad_name} | {selectedReport.channel_name || "N/A"}
              </Typography>

              <Typography variant="body2">
                Capture Status: {selectedReport.capture_status || "N/A"}
              </Typography>

              <Typography variant="body2">
                Interruption Time: {selectedReport.interruption_time || "N/A"}
              </Typography>

              <Typography variant="body2">
                Interruption Reason: {selectedReport.interruption_reason || "N/A"}
              </Typography>

              {selectedReport.screenshot_url ? (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Screenshot Proof
                  </Typography>
                  <Box
                    component="img"
                    src={selectedReport.screenshot_url}
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
                <Typography>No screenshot evidence available.</Typography>
              )}

              {selectedReport.screenshot_url && (
                <Button
                  variant="outlined"
                  component="a"
                  href={selectedReport.screenshot_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open Screenshot
                </Button>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEvidenceOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Export Dialog (unchanged) */}
      <Dialog open={exportPromptOpen} onClose={() => setExportPromptOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Select Export Format</DialogTitle>
        <DialogContent dividers>
          <TextField
            select
            fullWidth
            label="Format"
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value)}
          >
            <MenuItem value="csv">CSV</MenuItem>
            <MenuItem value="excel">Excel</MenuItem>
            <MenuItem value="pdf">PDF</MenuItem>
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setExportPromptOpen(false)}>Cancel</Button>
          <Button variant="contained" disabled={exporting} onClick={handleExportAction}>
            {exporting ? "Exporting..." : "Continue"}
          </Button>
        </DialogActions>
      </Dialog>
    </AppLayout>
  );
};

export default ReportsPage;
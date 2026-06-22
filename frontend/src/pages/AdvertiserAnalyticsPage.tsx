import React from "react";
import { Alert, Button, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";

const AdvertiserAnalyticsPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <AppLayout title="Advertisers">
      <Typography variant="h4" gutterBottom>
        Advertisers
      </Typography>

      <Alert severity="info" sx={{ mb: 3 }}>
        Advertisers and advertisement videos are now managed together from the Ad
        Library. This keeps each advertiser linked to all their uploaded reference
        videos in one review flow.
      </Alert>

      <Button variant="contained" onClick={() => navigate("/ad-library")}>
        Open Ad Library
      </Button>
    </AppLayout>
  );
};

export default AdvertiserAnalyticsPage;
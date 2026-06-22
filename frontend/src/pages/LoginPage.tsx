//LoginPage.tsx 
import React, { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Container,
  TextField,
  Typography,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";

const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("admin@dtv.com");
  const [password, setPassword] = useState("Admin123!");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <Card sx={{ width: "100%", boxShadow: 4 }}>
          <CardContent sx={{ p: 4 }}>
            <Typography variant="h4" gutterBottom>
              DTV-Ad Monitor
            </Typography>
            <Typography variant="body1" sx={{ mb: 3 }}>
              Sign in to access your role-based dashboard.
            </Typography>

            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            <Box component="form" onSubmit={handleSubmit}>
              <TextField
                fullWidth
                label="Email"
                margin="normal"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <TextField
                fullWidth
                type="password"
                label="Password"
                margin="normal"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />

              <Button
                fullWidth
                type="submit"
                variant="contained"
                size="large"
                sx={{ mt: 2 }}
                disabled={submitting}
              >
                {submitting ? "Signing in..." : "Login"}
              </Button>
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
};

export default LoginPage;
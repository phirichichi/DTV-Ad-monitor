//USerPage.tsx 
import React, { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
import { apiClient } from "../api/client";

type UserRole = "admin" | "operator" | "client";

type UserRow = {
  id: number;
  email: string;
  role?: string | null;
  is_active: boolean;
  last_login_at?: string | null;
  current_session_active?: boolean | null;
  current_session_started_at?: string | null;
};

type LoginHistoryItem = {
  id: number;
  login_at: string | null;
  logout_at: string | null;
  ip_address: string | null;
  user_agent: string | null;
  is_current_session: boolean;
};

type LoginHistoryResponse = {
  user_id: number;
  email: string;
  history: LoginHistoryItem[];
};

const UsersPage: React.FC = () => {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [roleName, setRoleName] = useState<UserRole>("operator");

  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [actionUserId, setActionUserId] = useState<number | null>(null);

  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedHistory, setSelectedHistory] = useState<LoginHistoryResponse | null>(null);

  const loadUsers = async () => {
    try {
      setError("");
      const response = await apiClient.get<UserRow[]>("/api/v1/users");
      setUsers(response.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const resetForm = () => {
    setEmail("");
    setPassword("");
    setRoleName("operator");
  };

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setInfo("");

    if (!email.trim()) {
      setError("Email is required.");
      return;
    }

    if (!password.trim()) {
      setError("Password is required.");
      return;
    }

    setCreating(true);

    try {
      await apiClient.post("/api/v1/users", {
        email: email.trim(),
        password,
        role_name: roleName,
        is_active: true,
      });

      resetForm();
      await loadUsers();
      setInfo("User created successfully.");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to create user");
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (user: UserRow) => {
    setError("");
    setInfo("");
    setActionUserId(user.id);

    try {
      await apiClient.patch(`/api/v1/users/${user.id}/status`, {
        is_active: !user.is_active,
      });

      setInfo(
        `User "${user.email}" ${!user.is_active ? "activated" : "deactivated"} successfully.`
      );
      await loadUsers();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to update user status");
    } finally {
      setActionUserId(null);
    }
  };

  const handleDeleteClick = async (user: UserRow) => {
    setError("");
    setInfo("");

    const confirmed = window.confirm(`Delete user "${user.email}"? This cannot be undone.`);
    if (!confirmed) {
      return;
    }

    setActionUserId(user.id);

    try {
      await apiClient.delete(`/api/v1/users/${user.id}`);
      setInfo(`User "${user.email}" deleted successfully.`);
      await loadUsers();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to delete user");
    } finally {
      setActionUserId(null);
    }
  };

  const handleShowHistory = async (user: UserRow) => {
    setError("");
    setInfo("");
    setSelectedHistory(null);
    setHistoryOpen(true);
    setHistoryLoading(true);

    try {
      const response = await apiClient.get<LoginHistoryResponse>(
        `/api/v1/users/${user.id}/login-history`
      );
      setSelectedHistory(response.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load login history");
      setHistoryOpen(false);
    } finally {
      setHistoryLoading(false);
    }
  };

  return (
    <AppLayout title="Users">
      <Typography variant="h4" gutterBottom>
        Users
      </Typography>

      <Typography sx={{ mb: 3 }}>
        Create users, assign roles, activate or deactivate accounts, delete users, and review login history.
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
        sx={{ mb: 4, display: "grid", gap: 2, maxWidth: 500 }}
      >
        <TextField
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <TextField
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <TextField
          select
          label="Role"
          value={roleName}
          onChange={(e) => setRoleName(e.target.value as UserRole)}
        >
          <MenuItem value="admin">admin</MenuItem>
          <MenuItem value="operator">operator</MenuItem>
          <MenuItem value="client">client</MenuItem>
        </TextField>

        <Button type="submit" variant="contained" disabled={creating}>
          {creating ? "Creating..." : "Create User"}
        </Button>
      </Box>

      {loading ? (
        <CircularProgress />
      ) : (
        <List>
          {users.map((user) => (
            <ListItem
              key={user.id}
              divider
              secondaryAction={
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2">Active</Typography>

                  <Switch
                    checked={user.is_active}
                    disabled={actionUserId === user.id}
                    onChange={() => handleToggleActive(user)}
                  />

                  <Button
                    size="small"
                    variant="outlined"
                    disabled={actionUserId === user.id}
                    onClick={() => handleShowHistory(user)}
                  >
                    Login History
                  </Button>

                  <Button
                    size="small"
                    color="error"
                    variant="outlined"
                    disabled={actionUserId === user.id}
                    onClick={() => handleDeleteClick(user)}
                  >
                    Delete
                  </Button>
                </Stack>
              }
            >
              <ListItemText
                primary={user.email}
                secondary={
                  <>
                    <div>Role: {user.role || "None"}</div>
                    <div>Active: {user.is_active ? "Yes" : "No"}</div>
                    <div>Logged in now: {user.current_session_active ? "Yes" : "No"}</div>
                    <div>Last login: {user.last_login_at || "N/A"}</div>
                    <div>
                      Current session started: {user.current_session_started_at || "N/A"}
                    </div>
                  </>
                }
              />
            </ListItem>
          ))}

          {users.length === 0 && (
            <ListItem>
              <ListItemText primary="No users found." />
            </ListItem>
          )}
        </List>
      )}

      <Dialog open={historyOpen} onClose={() => setHistoryOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>
          Login History{selectedHistory ? ` — ${selectedHistory.email}` : ""}
        </DialogTitle>

        <DialogContent dividers>
          {historyLoading && <CircularProgress />}

          {!historyLoading && selectedHistory && selectedHistory.history.length === 0 && (
            <Typography>No login history found for this user.</Typography>
          )}

          {!historyLoading && selectedHistory && selectedHistory.history.length > 0 && (
            <List>
              {selectedHistory.history.map((item) => (
                <ListItem key={item.id} divider>
                  <ListItemText
                    primary={`Login: ${item.login_at || "N/A"}`}
                    secondary={
                      <>
                        <div>Logout: {item.logout_at || "N/A"}</div>
                        <div>IP Address: {item.ip_address || "N/A"}</div>
                        <div>Current Session: {item.is_current_session ? "Yes" : "No"}</div>
                        <div>User Agent: {item.user_agent || "N/A"}</div>
                      </>
                    }
                  />
                </ListItem>
              ))}
            </List>
          )}
        </DialogContent>

        <DialogActions>
          <Button onClick={() => setHistoryOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </AppLayout>
  );
};

export default UsersPage;
//AppLayout.tsx 
import React from "react";
import {
  AppBar,
  Box,
  Chip,
  CssBaseline,
  Drawer,
  List,
  ListItemButton,
  ListItemText,
  Toolbar,
  Typography,
  Button,
} from "@mui/material";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";

const drawerWidth = 280;

type MenuItem = {
  label: string;
  path: string;
};

const menuByRole: Record<string, MenuItem[]> = {
  admin: [
    { label: "Dashboard", path: "/dashboard" },
    { label: "Users", path: "/users" },
    { label: "Channels", path: "/channels" },
    { label: "Advertisers", path: "/advertisers" },
    { label: "Ad Library", path: "/ads" },
    { label: "Monitoring", path: "/monitoring" },
    { label: "Reports", path: "/reports" },
    { label: "Operations Health", path: "/operations-health" },
  ],
  operator: [
    { label: "Dashboard", path: "/dashboard" },
    { label: "Monitoring", path: "/monitoring" },
    { label: "Reports", path: "/reports" },
    { label: "Ad Library", path: "/ads" },
    { label: "Operations Health", path: "/operations-health" },
  ],
  client: [
    { label: "Dashboard", path: "/dashboard" },
    { label: "Advertisers", path: "/advertisers" },
    { label: "Reports", path: "/reports" },
  ],
};

export const AppLayout: React.FC<{ children: React.ReactNode; title?: string }> = ({
  children,
  title = "DTV-Ad Monitor",
}) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const items = user ? menuByRole[user.role] || [] : [];

  return (
    <Box sx={{ display: "flex" }}>
      <CssBaseline />

      <AppBar position="fixed" sx={{ zIndex: 1300 }}>
        <Toolbar sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
          <Box>
            <Typography variant="h6">{title}</Typography>
            {user && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.5 }}>
                <Typography variant="body2">{user.email}</Typography>
                <Chip label={user.role.toUpperCase()} size="small" color="secondary" />
              </Box>
            )}
          </Box>

          <Button
            color="inherit"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            Logout
          </Button>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: {
            width: drawerWidth,
            boxSizing: "border-box",
          },
        }}
      >
        <Toolbar />
        <Box sx={{ overflow: "auto", p: 1 }}>
          <Typography variant="subtitle2" sx={{ px: 2, py: 1, color: "text.secondary" }}>
            Navigation
          </Typography>
          <List>
            {items.map((item) => (
              <ListItemButton
                key={item.path}
                selected={location.pathname === item.path}
                onClick={() => navigate(item.path)}
                sx={{ borderRadius: 1 }}
              >
                <ListItemText primary={item.label} />
              </ListItemButton>
            ))}
          </List>
        </Box>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
};
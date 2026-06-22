//ProtectReoute.ts x 
import React from "react";
import { Navigate } from "react-router-dom";
import { CircularProgress, Box } from "@mui/material";
import { useAuth } from "../../features/auth/AuthContext";

interface ProtectedRouteProps {
  children: React.ReactElement;
  allowedRoles?: Array<"admin" | "operator" | "client">;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
}) => {
  const { user, loading, isAuthenticated } = useAuth();

  if (loading) {
    return (
      <Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role as "admin" | "operator" | "client")) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};
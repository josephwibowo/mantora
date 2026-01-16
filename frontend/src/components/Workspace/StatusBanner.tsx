import { Box, Typography, alpha } from "@mui/material";
import { ReactNode } from "react";

export interface StatusBannerProps {
  variant: "warning" | "error" | "success" | "info";
  icon: ReactNode;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
}

export function StatusBanner({
  variant,
  icon,
  title,
  description,
  children,
}: StatusBannerProps) {
  return (
    <Box
      sx={{
        display: "flex",
        gap: 2,
        p: 2,
        borderRadius: 1,
        bgcolor: (theme) => alpha(theme.palette[variant].main, 0.1),
        border: "1px solid",
        borderColor: `${variant}.main`,
        alignItems: "flex-start",
      }}
    >
      <Box sx={{ mt: 0.5, color: `${variant}.main`, display: "flex" }}>
        {icon}
      </Box>

      <Box sx={{ flexGrow: 1 }}>
        <Typography
          variant="subtitle2"
          sx={{ fontWeight: 600, color: `${variant}.light`, mb: 0.5 }}
        >
          {title}
        </Typography>

        {description && (
          <Typography
            variant="body2"
            sx={{ color: "text.secondary", mb: children ? 2 : 0 }}
          >
            {description}
          </Typography>
        )}

        {children}
      </Box>
    </Box>
  );
}

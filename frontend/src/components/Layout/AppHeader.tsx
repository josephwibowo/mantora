import {
  AppBar,
  Box,
  IconButton,
  Toolbar,
  Typography,
  useTheme,
} from "@mui/material";
import { useContext } from "react";
import { Link } from "react-router-dom";
import { StatePill } from "../StatePill";
import { ColorModeContext } from "../../theme/ColorModeContext";
import { ProtectiveModeBadge } from "./ProtectiveModeBadge";

// Icons
import DarkModeIcon from "@mui/icons-material/DarkMode";
import LightModeIcon from "@mui/icons-material/LightMode";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";

// Types
import type { ObservedStep } from "../../api/types";

interface AppHeaderProps {
  title?: string;
  steps?: ObservedStep[];
  showBack?: boolean;
  actions?: React.ReactNode;
}

export function AppHeader({
  title = "Mantora",
  steps = [],
  showBack = false,
  actions,
}: AppHeaderProps) {
  const theme = useTheme();
  const colorMode = useContext(ColorModeContext);

  return (
    <AppBar
      position="static"
      color="default"
      sx={{ borderBottom: 1, borderColor: "divider" }}
      elevation={0}
    >
      <Toolbar variant="dense">
        <Box
          sx={{ display: "flex", alignItems: "center", gap: 2, flexGrow: 1 }}
        >
          {showBack && (
            <IconButton component={Link} to="/" size="small" edge="start">
              <ArrowBackIcon fontSize="small" />
            </IconButton>
          )}

          <Typography
            variant="body1"
            noWrap
            component="div"
            sx={{ fontWeight: 600, fontFamily: "monospace" }}
          >
            {title}
          </Typography>

          {steps.length > 0 && <StatePill steps={steps} />}
        </Box>

        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <ProtectiveModeBadge />
          {actions}
          <IconButton
            onClick={colorMode.toggleColorMode}
            color="inherit"
            size="small"
          >
            {theme.palette.mode === "dark" ? (
              <LightModeIcon fontSize="small" />
            ) : (
              <DarkModeIcon fontSize="small" />
            )}
          </IconButton>
        </Box>
      </Toolbar>
    </AppBar>
  );
}

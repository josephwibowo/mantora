import { Box, Popover, Stack, Typography, alpha } from "@mui/material";
import SecurityIcon from "@mui/icons-material/Security";
import { useState } from "react";
import { useSettings } from "../../api/queries";

export function ProtectiveModeBadge() {
  const settings = useSettings();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const handleOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const open = Boolean(anchorEl);

  if (settings.isLoading || !settings.data) {
    return null; // Or a skeleton/placeholder
  }

  const isProtective = settings.data.safety_mode === "protective";
  const badgeColor = isProtective ? "success" : "warning";

  return (
    <>
      <Box
        onClick={handleOpen}
        onMouseEnter={handleOpen}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 0.5,
          px: 1,
          py: 0.5,
          borderRadius: 1,
          cursor: "pointer",
          color: `${badgeColor}.main`,
          bgcolor: (theme) => alpha(theme.palette[badgeColor].main, 0.1),
          border: 1,
          borderColor: "transparent",
          "&:hover": {
            bgcolor: (theme) => alpha(theme.palette[badgeColor].main, 0.2),
            borderColor: "divider",
          },
          transition: "all 0.2s",
        }}
      >
        <SecurityIcon fontSize="small" color="inherit" />
        <Typography variant="caption" fontWeight={700} color="inherit">
          {isProtective ? "PROTECTIVE MODE" : "TRANSPARENT"}
        </Typography>
      </Box>

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "center",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "center",
        }}
        sx={{ pointerEvents: "none", mt: 1 }}
        slotProps={{
          paper: {
            onMouseEnter: () => setAnchorEl(anchorEl),
            onMouseLeave: handleClose,
            sx: { pointerEvents: "auto", p: 2, maxWidth: 400 },
          },
        }}
      >
        <Stack spacing={1.5}>
          <Typography variant="subtitle2" fontWeight={700}>
            {isProtective ? "🛡️ Protective Mode" : "⚠️ Transparent Mode"}
          </Typography>

          {isProtective && settings.data.active_rules.length > 0 && (
            <Box>
              <Typography
                variant="caption"
                color="text.secondary"
                fontWeight={600}
                display="block"
                mb={0.5}
              >
                ACTIVE POLICY RULES
              </Typography>
              <Stack spacing={0.5}>
                {settings.data.active_rules.map((rule) => (
                  <Box key={rule.id}>
                    <Typography
                      variant="body2"
                      fontWeight={600}
                      color="success.main"
                    >
                      ✓ {rule.label}
                    </Typography>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ ml: 2, display: "block" }}
                    >
                      {rule.description}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </Box>
          )}

          {!isProtective && (
            <Typography variant="body2" color="warning.main">
              No blocking rules active. Queries are logged but not restricted.
            </Typography>
          )}

          <Box sx={{ pt: 1, borderTop: 1, borderColor: "divider" }}>
            <Typography
              variant="caption"
              color="text.secondary"
              fontWeight={600}
            >
              LIMITS
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              display="block"
            >
              • Preview: {settings.data.limits.max_preview_rows} rows
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              display="block"
            >
              • Payload:{" "}
              {Math.round(
                settings.data.limits.max_preview_payload_bytes / 1024,
              )}{" "}
              KB
            </Typography>
          </Box>
        </Stack>
      </Popover>
    </>
  );
}

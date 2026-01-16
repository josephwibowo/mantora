import {
  Box,
  Chip,
  IconButton,
  Paper,
  Tooltip,
  Typography,
} from "@mui/material";
import { ReactNode } from "react";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import CodeIcon from "@mui/icons-material/Code";

interface ArtifactTileProps {
  title: string;
  type: string;
  children: ReactNode;
  onCopyMarkdown?: () => void;
  onCopySQL?: () => void;
}

export function ArtifactTile({
  title,
  type,
  children,
  onCopyMarkdown,
  onCopySQL,
}: ArtifactTileProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        mb: 3,
        borderColor: "divider",
      }}
    >
      {/* Header */}
      <Box
        sx={{
          p: 1.5,
          borderBottom: 1,
          borderColor: "divider",
          bgcolor: "action.hover",
          display: "flex",
          alignItems: "center",
          gap: 2,
        }}
      >
        <Chip
          label={type}
          size="small"
          sx={{
            fontSize: "0.65rem",
            height: 20,
            borderRadius: 1,
            fontWeight: 600,
          }}
        />

        <Typography variant="subtitle2" sx={{ fontWeight: 600, flexGrow: 1 }}>
          {title}
        </Typography>

        <Box sx={{ display: "flex", gap: 0.5 }}>
          {onCopySQL && (
            <Tooltip title="Copy SQL">
              <IconButton size="small" onClick={onCopySQL}>
                <CodeIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {onCopyMarkdown && (
            <Tooltip title="Copy Markdown">
              <IconButton size="small" onClick={onCopyMarkdown}>
                <ContentCopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Box>

      {/* Content */}
      <Box sx={{ p: 0, overflow: "auto" }}>{children}</Box>
    </Paper>
  );
}

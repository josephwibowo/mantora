import { Box, Paper, Typography } from "@mui/material";
import { PrismAsyncLight as SyntaxHighlighter } from "react-syntax-highlighter";
import json from "react-syntax-highlighter/dist/esm/languages/prism/json";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

SyntaxHighlighter.registerLanguage("json", json);

interface JsonViewerProps {
  label?: string;
  data: unknown;
}

export function JsonViewer({ label, data }: JsonViewerProps) {
  // currently we only import one theme, but could toggle based on isDark
  const highlightStyle = vscDarkPlus;

  return (
    <Paper variant="outlined" sx={{ overflow: "hidden" }}>
      {label && (
        <Box
          sx={{
            px: 2,
            py: 1,
            borderBottom: 1,
            borderColor: "divider",
            bgcolor: "action.hover",
          }}
        >
          <Typography variant="caption" fontWeight={700}>
            {label}
          </Typography>
        </Box>
      )}
      <SyntaxHighlighter
        language="json"
        style={highlightStyle}
        customStyle={{ margin: 0, padding: 16, fontSize: "0.85rem" }}
      >
        {JSON.stringify(data, null, 2) ?? ""}
      </SyntaxHighlighter>
    </Paper>
  );
}

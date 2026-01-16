import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  Typography,
} from "@mui/material";

import type { PendingRequest } from "../api/types";

function extractSql(p: PendingRequest): string | null {
  const args = p.arguments;
  if (!args || typeof args !== "object") return null;
  // backend stores arguments as {"sql": "..."} for query blockers
  const record = args as Record<string, unknown>;
  return typeof record.sql === "string" ? record.sql : null;
}

export function BlockerModal(props: {
  pendingRequests: PendingRequest[];
  onAllow: (requestId: string) => void;
  onDeny: (requestId: string) => void;
  isLoading?: boolean;
}) {
  const { pendingRequests, onAllow, onDeny, isLoading } = props;
  const open = pendingRequests.length > 0;
  const current = pendingRequests[0];

  if (!current) return null;

  const sql = extractSql(current);

  return (
    <Dialog open={open} maxWidth="md" fullWidth>
      <DialogTitle>Blocked: approval required</DialogTitle>
      <DialogContent>
        <Stack spacing={1}>
          <Typography variant="body2" color="text.secondary">
            Mantora Protective Mode blocked a risky operation. Review and choose
            Allow or Deny.
          </Typography>

          <Divider />

          <Typography variant="subtitle2">Reason</Typography>
          <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
            {current.reason ?? "Blocked by policy"}
          </Typography>

          {sql && (
            <>
              <Typography variant="subtitle2" sx={{ mt: 1 }}>
                SQL
              </Typography>
              <Typography
                component="pre"
                variant="body2"
                sx={{
                  m: 0,
                  p: 1,
                  borderRadius: 1,
                  bgcolor: (theme) =>
                    theme.palette.mode === "dark" ? "grey.900" : "grey.100",
                  color: "text.primary",
                  fontFamily: "monospace",
                  whiteSpace: "pre-wrap",
                }}
              >
                {sql}
              </Typography>
            </>
          )}

          {pendingRequests.length > 1 && (
            <Typography variant="caption" color="text.secondary">
              Queue: {pendingRequests.length} blocked requests pending
            </Typography>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button
          onClick={() => onDeny(current.id)}
          color="error"
          disabled={isLoading}
        >
          Deny
        </Button>
        <Button
          onClick={() => onAllow(current.id)}
          variant="contained"
          disabled={isLoading}
        >
          Allow
        </Button>
      </DialogActions>
    </Dialog>
  );
}

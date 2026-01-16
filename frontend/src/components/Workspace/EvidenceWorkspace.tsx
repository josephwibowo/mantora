import { Alert, Box, Button, Divider, Stack, Typography } from "@mui/material";
import BlockIcon from "@mui/icons-material/Block";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";

import { StatusBanner } from "./StatusBanner";
import { JsonViewer } from "../JsonViewer";

import type { Cast, ObservedStep, PendingRequest } from "../../api/types";
import { CastRenderer } from "../CastRenderer";
import { isBlockerDecisionArgs } from "../../utils/guards";

interface EvidenceWorkspaceProps {
  step?: ObservedStep;
  cast?: Cast;
  pendingRequest?: PendingRequest;
  onAllow?: (requestId: string) => void;
  onDeny?: (requestId: string) => void;
  isDecisionLoading?: boolean;
}

export function EvidenceWorkspace({
  step,
  cast,
  pendingRequest,
  onAllow,
  onDeny,
  isDecisionLoading,
}: EvidenceWorkspaceProps) {
  if (!step) {
    return (
      <Box
        sx={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          color: "text.secondary",
          bgcolor: "background.default",
        }}
      >
        <Typography variant="h6" gutterBottom>
          Select a step to inspect
        </Typography>
        <Typography variant="body2">
          Click any item in the timeline to view details and evidence.
        </Typography>
      </Box>
    );
  }

  const copyEvidence = () => {
    const evidence = {
      step,
      cast,
      pendingRequest,
    };
    navigator.clipboard.writeText(JSON.stringify(evidence, null, 2));
  };

  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "background.default",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 3,
          py: 2,
          borderBottom: 1,
          borderColor: "divider",
          bgcolor: "background.paper",
        }}
      >
        <Stack spacing={0.5}>
          {/* Metadata Bar: NAME • STATUS • TIME • DURATION */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              color: "text.secondary",
              fontSize: "0.75rem",
              fontFamily: "monospace",
            }}
          >
            <Typography
              variant="inherit"
              component="span"
              fontWeight={700}
              sx={{ color: "primary.main" }}
            >
              {step.name.toUpperCase()}
            </Typography>

            <span>•</span>

            <Typography
              variant="inherit"
              component="span"
              sx={{
                color: step.status === "error" ? "error.main" : "success.main",
                fontWeight: 600,
              }}
            >
              {step.status === "error" ? "ERROR" : "OK"}
            </Typography>

            <span>•</span>

            <span>{new Date(step.created_at).toLocaleTimeString()}</span>

            {step.duration_ms !== undefined && (
              <>
                <span>•</span>
                <span>{step.duration_ms}ms</span>
              </>
            )}

            <Box sx={{ flexGrow: 1 }} />

            <Button
              startIcon={<ContentCopyIcon />}
              size="small"
              onClick={copyEvidence}
              sx={{
                color: "text.secondary",
                minWidth: "auto",
                px: 1,
                textTransform: "none",
              }}
            >
              JSON
            </Button>
          </Box>

          {/* Main Narrative Title */}
          <Typography variant="h6" fontWeight={600} sx={{ lineHeight: 1.3 }}>
            {/* Use simple heuristics or just step.name/summary if available. 
                             Using summary if present is best, else name. 
                         */}
            {step.summary ||
              (step.kind === "tool_call" ? `Executed ${step.name}` : step.kind)}
          </Typography>
        </Stack>
      </Box>

      {/* Scrollable Content */}
      <Box sx={{ flexGrow: 1, overflow: "auto", p: 3 }}>
        <Stack spacing={4}>
          {/* Blocker Action Area */}
          {/* Blocker Action Area */}
          {(step.kind === "blocker" || pendingRequest) && (
            <StatusBanner
              variant="warning"
              icon={<WarningAmberIcon />}
              title="Action Blocked"
              description={
                pendingRequest?.reason ||
                step.summary ||
                "This action requires approval."
              }
            >
              {pendingRequest && pendingRequest.status === "pending" && (
                <Stack direction="row" spacing={2}>
                  <Button
                    variant="outlined"
                    color="success"
                    size="small"
                    startIcon={<PlayArrowIcon />}
                    onClick={() => onAllow?.(pendingRequest.id)}
                    disabled={isDecisionLoading}
                    sx={{
                      bgcolor: "background.paper",
                      "&:hover": { bgcolor: "success.dark", color: "white" },
                    }}
                  >
                    Allow
                  </Button>
                  <Button
                    variant="outlined"
                    color="error"
                    size="small"
                    startIcon={<StopIcon />}
                    onClick={() => onDeny?.(pendingRequest.id)}
                    disabled={isDecisionLoading}
                    sx={{
                      bgcolor: "background.paper",
                      "&:hover": { bgcolor: "error.dark", color: "white" },
                    }}
                  >
                    Deny
                  </Button>
                </Stack>
              )}
              {pendingRequest && pendingRequest.status !== "pending" && (
                <Alert
                  severity={
                    pendingRequest.status === "allowed" ? "success" : "error"
                  }
                  sx={{
                    bgcolor: "background.paper",
                    border: 1,
                    borderColor: "divider",
                  }}
                >
                  Decision: {pendingRequest.status.toUpperCase()}
                </Alert>
              )}
            </StatusBanner>
          )}

          {/* Denied Decision Banner */}
          {step.kind === "blocker_decision" &&
            isBlockerDecisionArgs(step.args) &&
            step.args.decision === "denied" && (
              <StatusBanner
                variant="error"
                icon={<BlockIcon />}
                title="Action Denied"
                description={step.args.reason || "This action was denied."}
              />
            )}

          {/* CAST (Visual Artifact) */}
          {cast && (
            <Box>
              <Typography
                variant="overline"
                color="text.secondary"
                fontWeight={700}
                sx={{ mb: 1, display: "block" }}
              >
                ARTIFACT
              </Typography>
              <CastRenderer cast={cast} />
            </Box>
          )}

          {/* EVIDENCE (Input/Output) */}
          <Divider sx={{ my: 1, opacity: 0.5 }} />
          <Typography
            variant="overline"
            color="text.secondary"
            fontWeight={700}
            sx={{ mb: 1, display: "block" }}
          >
            EVIDENCE
          </Typography>

          <Stack spacing={2}>
            <JsonViewer label="INPUT (ARGS)" data={step.args} />
            {!!step.result && <JsonViewer label="RESULT" data={step.result} />}
          </Stack>
        </Stack>
      </Box>
    </Box>
  );
}

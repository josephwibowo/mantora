import {
  Alert,
  Box,
  CircularProgress,
  Typography,
  List,
  ListItemButton,
  ListItemText,
  Button,
} from "@mui/material";
import DescriptionIcon from "@mui/icons-material/Description";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import type { ObservedStep } from "../api/types";
import { subscribeToSteps } from "../api/sse";
import {
  useAllowPending,
  useCasts,
  useDenyPending,
  usePendingRequests,
  useSession,
  useSessions,
  useSteps,
} from "../api/queries";
import { ApiError } from "../api/client";
import { BlockerModal } from "../components/BlockerModal";
import { DashboardLayout } from "../components/Layout/DashboardLayout";
import { RightPanel } from "../components/RightPanel/RightPanel";
import { TimelineFeed } from "../components/RightPanel/Timeline/TimelineFeed";
import { SessionStatsBar } from "../components/SessionStatsBar";
import { EvidenceWorkspace } from "../components/Workspace/EvidenceWorkspace";

export function SessionDetailPage() {
  const params = useParams();
  const navigate = useNavigate();
  const sessionId = params.sessionId ?? "";

  const queryClient = useQueryClient();
  const session = useSession(sessionId);
  const steps = useSteps(sessionId);
  const casts = useCasts(sessionId, { refetchInterval: 10000 });
  const pendingRequests = usePendingRequests(sessionId, {
    refetchInterval: 10000,
  });
  const allowPending = useAllowPending(sessionId);
  const denyPending = useDenyPending(sessionId);

  // Sidebar data
  const allSessions = useSessions();

  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);

  const handleStepSelect = useCallback((stepId: string) => {
    setSelectedStepId(stepId);
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    return subscribeToSteps(sessionId, (step) => {
      queryClient.setQueryData<ObservedStep[]>(
        ["steps", sessionId],
        (prev: ObservedStep[] | undefined) => {
          const next = [...(prev ?? []), step];
          return next.length > 1000 ? next.slice(next.length - 1000) : next;
        },
      );
      if (step.kind === "blocker") {
        queryClient.invalidateQueries({ queryKey: ["pending", sessionId] });
      }
      if (step.name.startsWith("cast_")) {
        queryClient.invalidateQueries({ queryKey: ["casts", sessionId] });
      }
    });
  }, [queryClient, sessionId]);

  const stepsData = useMemo(() => steps.data ?? [], [steps.data]);
  const selectedStep = stepsData.find((s) => s.id === selectedStepId);

  // Find cast for selected step
  const activeCast = casts.data?.find(
    (c) => c.origin_step_id === selectedStepId,
  );

  // Find pending request for selected step (if blocker)
  const activePendingRequest = pendingRequests.data?.find(
    (p) => p.blocker_step_id === selectedStepId,
  );

  // Calculate summary
  const summary = useMemo(() => {
    return stepsData.reduce(
      (acc, s) => {
        if (s.kind === "tool_call") acc.tool_calls++;
        // queries count
        if (s.name === "query" || s.name === "cast_table") acc.queries++;
        // casts count
        if (["cast_table", "cast_chart", "cast_note"].includes(s.name))
          acc.casts++;
        if (s.kind === "blocker") acc.blocks++;
        if (s.status === "error") acc.errors++;
        if (s.warnings) acc.warnings += s.warnings?.length ?? 0;
        return acc;
      },
      {
        tool_calls: 0,
        queries: 0,
        casts: 0,
        blocks: 0,
        errors: 0,
        warnings: 0,
      },
    );
  }, [stepsData]);

  // -- Sidebar Component --
  const Sidebar = (
    <Box
      sx={{
        height: "100%",
        overflow: "auto",
        bgcolor: "background.paper",
        borderRight: 1,
        borderColor: "divider",
      }}
    >
      <Box sx={{ p: 2, pb: 1 }}>
        <Typography variant="caption" fontWeight={600} color="text.secondary">
          RECENT SESSIONS
        </Typography>
      </Box>
      <List dense>
        {(allSessions.data ?? []).slice(0, 20).map((s) => (
          <ListItemButton
            key={s.id}
            selected={s.id === sessionId}
            onClick={() => navigate(`/sessions/${s.id}`)}
            sx={{
              borderLeft: 3,
              borderLeftColor: "transparent",
              "&.Mui-selected": { borderLeftColor: "primary.main" },
            }}
          >
            <ListItemText
              primary={s.title || "Untitled"}
              primaryTypographyProps={{
                variant: "body2",
                noWrap: true,
                fontWeight: s.id === sessionId ? 600 : 400,
              }}
              secondary={new Date(s.created_at).toLocaleDateString()}
            />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );

  // -- Main Content (Evidence Workspace) --
  const Main = (
    <EvidenceWorkspace
      step={selectedStep}
      cast={activeCast}
      pendingRequest={activePendingRequest}
      onAllow={(id) => allowPending.mutate(id)}
      onDeny={(id) => denyPending.mutate(id)}
      isDecisionLoading={allowPending.isPending || denyPending.isPending}
    />
  );

  // -- Right Panel (Timeline) --
  const Right = (
    <RightPanel>
      <TimelineFeed
        steps={stepsData}
        selectedStepId={selectedStepId ?? undefined}
        onStepSelect={handleStepSelect}
      />
    </RightPanel>
  );

  // Early returns must stay below all Hooks
  if (!sessionId) return <Alert severity="error">Missing session id</Alert>;
  if (session.isLoading || steps.isLoading)
    return (
      <Box
        sx={{
          display: "flex",
          height: "100vh",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <CircularProgress />
      </Box>
    );
  if (session.error) {
    if (session.error instanceof ApiError && session.error.status === 404) {
      return (
        <Box
          sx={{
            display: "flex",
            height: "100vh",
            alignItems: "center",
            justifyContent: "center",
            flexDirection: "column",
            gap: 2,
            bgcolor: "background.default",
          }}
        >
          <Typography variant="h4" fontWeight={700} color="text.secondary">
            Session Not Found
          </Typography>
          <Typography color="text.secondary">
            The session you are looking for does not exist or has been deleted.
          </Typography>
          <Button variant="contained" onClick={() => navigate("/")}>
            Go to Dashboard
          </Button>
        </Box>
      );
    }
    return <Alert severity="error">{(session.error as Error).message}</Alert>;
  }

  const handleExport = () => {
    window.location.href = `/api/sessions/${sessionId}/export.md`;
  };

  return (
    <>
      <DashboardLayout
        headerProps={{
          title: session.data?.title ?? "Untitled Session",
          steps: stepsData,
          showBack: true,
          actions: (
            <Button
              startIcon={<DescriptionIcon />}
              variant="outlined"
              size="small"
              onClick={handleExport}
              sx={{ borderColor: "divider", color: "text.secondary" }}
            >
              Export Receipt
            </Button>
          ),
        }}
        subheader={<SessionStatsBar summary={summary} />}
        sidebar={Sidebar}
        main={Main}
        rightPanel={Right}
      />

      <BlockerModal
        pendingRequests={pendingRequests.data ?? []}
        isLoading={allowPending.isPending || denyPending.isPending}
        onAllow={(id) => allowPending.mutate(id)}
        onDeny={(id) => denyPending.mutate(id)}
      />
    </>
  );
}

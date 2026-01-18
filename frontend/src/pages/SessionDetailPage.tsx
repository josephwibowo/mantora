import {
  Alert,
  Box,
  CircularProgress,
  Chip,
  InputBase,
  Paper,
  Stack,
  Typography,
  List,
  ListItemButton,
  ListItemText,
  Button,
} from '@mui/material';
import DescriptionIcon from '@mui/icons-material/Description';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';

import type { ObservedStep, StepCategory } from '../api/types';
import { subscribeToSteps } from '../api/sse';
import {
  useAllowPending,
  useCasts,
  useDenyPending,
  usePendingRequests,
  useSession,
  useSessions,
  useSteps,
} from '../api/queries';
import { ApiError } from '../api/client';
import { BlockerModal } from '../components/BlockerModal';
import { DashboardLayout } from '../components/Layout/DashboardLayout';
import { RightPanel } from '../components/RightPanel/RightPanel';
import { TimelineFeed } from '../components/RightPanel/Timeline/TimelineFeed';
import { SessionStatsBar } from '../components/SessionStatsBar';
import { EvidenceWorkspace } from '../components/Workspace/EvidenceWorkspace';
import {
  computeStepNarrative,
  extractSqlExcerpt,
  extractTableTouched,
  getStepCategory,
  getStepStatusLabel,
} from '../utils/stepUtils';

type StatusFilter = 'all' | 'ok' | 'error' | 'blocked' | 'allowed' | 'denied' | 'timeout';

export function SessionDetailPage() {
  const params = useParams();
  const navigate = useNavigate();
  const sessionId = params.sessionId ?? '';

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
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [categoryFilter, setCategoryFilter] = useState<StepCategory | 'all'>('all');
  const [searchFilter, setSearchFilter] = useState('');

  const handleStepSelect = useCallback((stepId: string) => {
    setSelectedStepId(stepId);
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    return subscribeToSteps(sessionId, (step) => {
      queryClient.setQueryData<ObservedStep[]>(
        ['steps', sessionId],
        (prev: ObservedStep[] | undefined) => {
          const next = [...(prev ?? []), step];
          return next.length > 1000 ? next.slice(next.length - 1000) : next;
        },
      );
      if (step.kind === 'blocker') {
        queryClient.invalidateQueries({ queryKey: ['pending', sessionId] });
      }
      if (step.name.startsWith('cast_')) {
        queryClient.invalidateQueries({ queryKey: ['casts', sessionId] });
      }
    });
  }, [queryClient, sessionId]);

  const stepsData = useMemo(() => steps.data ?? [], [steps.data]);
  const filteredSteps = useMemo(() => {
    const search = searchFilter.trim().toLowerCase();

    return stepsData.filter((step) => {
      if (categoryFilter !== 'all' && getStepCategory(step) !== categoryFilter) return false;

      const statusLabel = getStepStatusLabel(step);
      if (statusFilter !== 'all') {
        if (statusFilter === 'ok' && statusLabel !== 'OK') return false;
        if (statusFilter === 'error' && statusLabel !== 'ERROR') return false;
        if (statusFilter === 'blocked' && statusLabel !== 'BLOCKED') return false;
        if (statusFilter === 'allowed' && statusLabel !== 'ALLOWED') return false;
        if (statusFilter === 'denied' && statusLabel !== 'DENIED') return false;
        if (statusFilter === 'timeout' && statusLabel !== 'TIMEOUT') return false;
      }

      if (!search) return true;

      const narrative = computeStepNarrative(step).toLowerCase();
      const sql = (extractSqlExcerpt(step) ?? '').toLowerCase();
      const summary = (step.summary ?? '').toLowerCase();

      return (
        narrative.includes(search) ||
        sql.includes(search) ||
        summary.includes(search) ||
        step.name.toLowerCase().includes(search)
      );
    });
  }, [categoryFilter, searchFilter, statusFilter, stepsData]);
  const selectedStep = stepsData.find((s) => s.id === selectedStepId);

  // Find cast for selected step
  const activeCast = casts.data?.find((c) => c.origin_step_id === selectedStepId);

  // Find pending request for selected step (if blocker)
  const activePendingRequest = pendingRequests.data?.find(
    (p) => p.blocker_step_id === selectedStepId,
  );

  // Calculate summary
  const summary = useMemo(() => {
    const baseStats = stepsData.reduce(
      (acc, s) => {
        if (s.kind === 'tool_call') acc.tool_calls++;
        // queries count
        if (s.name === 'query' || s.name === 'cast_table') acc.queries++;
        // casts count
        if (['cast_table', 'cast_chart', 'cast_note'].includes(s.name)) acc.casts++;
        if (s.kind === 'blocker') acc.blocks++;
        if (getStepStatusLabel(s) === 'ALLOWED') acc.approvals++;
        if (s.status === 'error') acc.errors++;
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
        approvals: 0,
      },
    );

    const tables = new Set<string>();
    for (const step of stepsData) {
      const table = extractTableTouched(step);
      if (table) tables.add(table);
    }

    return {
      ...baseStats,
      touched_tables: Array.from(tables).sort(),
    };
  }, [stepsData]);

  // -- Sidebar Component --
  const Sidebar = (
    <Box
      sx={{
        height: '100%',
        overflow: 'auto',
        bgcolor: 'background.paper',
        borderRight: 1,
        borderColor: 'divider',
      }}
    >
      <Box sx={{ p: 2, pb: 1 }}>
        <Typography variant='caption' fontWeight={600} color='text.secondary'>
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
              borderLeftColor: 'transparent',
              '&.Mui-selected': { borderLeftColor: 'primary.main' },
            }}
          >
            <ListItemText
              primary={s.title || 'Untitled'}
              primaryTypographyProps={{
                variant: 'body2',
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
    <RightPanel
      controls={
        <Stack spacing={1}>
          <Stack direction='row' spacing={1} sx={{ flexWrap: 'wrap' }}>
            {(
              [
                ['all', 'ALL'],
                ['ok', 'OK'],
                ['error', 'ERROR'],
                ['blocked', 'BLOCKED'],
                ['allowed', 'ALLOWED'],
                ['denied', 'DENIED'],
                ['timeout', 'TIMEOUT'],
              ] as const
            ).map(([value, label]) => (
              <Chip
                key={value}
                label={label}
                size='small'
                variant={statusFilter === value ? 'filled' : 'outlined'}
                onClick={() => setStatusFilter(value)}
                sx={{ fontFamily: 'monospace', fontSize: '0.7rem', height: 22 }}
              />
            ))}
          </Stack>

          <Stack direction='row' spacing={1} sx={{ flexWrap: 'wrap' }}>
            {(
              [
                ['all', 'ALL'],
                ['query', 'QUERY'],
                ['schema', 'SCHEMA'],
                ['list', 'LIST'],
                ['cast', 'CAST'],
                ['unknown', 'UNKNOWN'],
              ] as const
            ).map(([value, label]) => (
              <Chip
                key={value}
                label={label}
                size='small'
                variant={categoryFilter === value ? 'filled' : 'outlined'}
                onClick={() => setCategoryFilter(value)}
                sx={{ fontFamily: 'monospace', fontSize: '0.7rem', height: 22 }}
              />
            ))}
          </Stack>

          <Paper
            elevation={0}
            variant='outlined'
            sx={{
              px: 1,
              py: 0.5,
              borderRadius: 1,
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            <InputBase
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder='Search SQL / narrative...'
              sx={{ fontSize: '0.8rem', fontFamily: 'monospace', width: '100%' }}
            />
          </Paper>

          <Typography variant='caption' color='text.secondary' fontFamily='monospace'>
            {filteredSteps.length} / {stepsData.length} steps
          </Typography>
        </Stack>
      }
    >
      <TimelineFeed
        steps={filteredSteps}
        selectedStepId={selectedStepId ?? undefined}
        onStepSelect={handleStepSelect}
      />
    </RightPanel>
  );

  // Early returns must stay below all Hooks
  if (!sessionId) return <Alert severity='error'>Missing session id</Alert>;
  if (session.isLoading || steps.isLoading)
    return (
      <Box
        sx={{
          display: 'flex',
          height: '100vh',
          alignItems: 'center',
          justifyContent: 'center',
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
            display: 'flex',
            height: '100vh',
            alignItems: 'center',
            justifyContent: 'center',
            flexDirection: 'column',
            gap: 2,
            bgcolor: 'background.default',
          }}
        >
          <Typography variant='h4' fontWeight={700} color='text.secondary'>
            Session Not Found
          </Typography>
          <Typography color='text.secondary'>
            The session you are looking for does not exist or has been deleted.
          </Typography>
          <Button variant='contained' onClick={() => navigate('/')}>
            Go to Dashboard
          </Button>
        </Box>
      );
    }
    return <Alert severity='error'>{(session.error as Error).message}</Alert>;
  }

  const handleExportMd = () => {
    window.location.href = `/api/sessions/${sessionId}/export.md`;
  };
  const handleExportJson = () => {
    window.location.href = `/api/sessions/${sessionId}/export.json`;
  };

  return (
    <>
      <DashboardLayout
        headerProps={{
          title: session.data?.title ?? 'Untitled Session',
          steps: stepsData,
          showBack: true,
          actions: (
            <Stack direction='row' spacing={1}>
              <Button
                startIcon={<DescriptionIcon />}
                variant='outlined'
                size='small'
                onClick={handleExportMd}
                sx={{ borderColor: 'divider', color: 'text.secondary' }}
              >
                Export Receipt
              </Button>
              <Button
                variant='outlined'
                size='small'
                onClick={handleExportJson}
                sx={{ borderColor: 'divider', color: 'text.secondary' }}
              >
                Export JSON
              </Button>
            </Stack>
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

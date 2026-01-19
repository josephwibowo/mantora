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
  ListSubheader,
  Button,
  Menu,
  MenuItem,
  ListItemIcon,
  Switch,
  Divider,
  IconButton,
  Tooltip,
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import DataObjectIcon from '@mui/icons-material/DataObject';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import CloseIcon from '@mui/icons-material/Close';
import CodeIcon from '@mui/icons-material/Code';
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
  useSessionReceipt,
  useSessionRollup,
  useSessions,
  useSteps,
  useUpdateSessionRepoRoot,
  useUpdateSessionTag,
} from '../api/queries';
import { ApiError } from '../api/client';
import { BlockerModal } from '../components/BlockerModal';
import { DashboardLayout } from '../components/Layout/DashboardLayout';
import { RightPanel } from '../components/RightPanel/RightPanel';
import { TimelineFeed } from '../components/RightPanel/Timeline/TimelineFeed';
import { SessionSummaryCard } from '../components/SessionSummaryCard';
import { SessionStatsBar } from '../components/SessionStatsBar';
import { EvidenceWorkspace } from '../components/Workspace/EvidenceWorkspace';
import { copyToClipboard } from '../utils/clipboard';
import {
  computeStepNarrative,
  extractSqlExcerpt,
  extractTableTouched,
  getStepCategory,
  getStepStatusLabel,
} from '../utils/stepUtils';

// Store preference key
const PREF_INCLUDE_DATA = 'mantora.export.includeData';

type StatusFilter = 'all' | 'ok' | 'error' | 'blocked' | 'allowed' | 'denied' | 'timeout';

export function SessionDetailPage() {
  const params = useParams();
  const navigate = useNavigate();
  const sessionId = params.sessionId ?? '';

  const queryClient = useQueryClient();
  const session = useSession(sessionId);
  const steps = useSteps(sessionId);
  const rollup = useSessionRollup(sessionId);
  const casts = useCasts(sessionId, { refetchInterval: 10000 });
  const pendingRequests = usePendingRequests(sessionId, {
    refetchInterval: 10000,
  });
  const allowPending = useAllowPending(sessionId);
  const denyPending = useDenyPending(sessionId);
  const receipt = useSessionReceipt(sessionId);
  const updateTag = useUpdateSessionTag(sessionId);
  const updateRepoRoot = useUpdateSessionRepoRoot(sessionId);

  // Sidebar data
  const allSessions = useSessions();

  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [categoryFilter, setCategoryFilter] = useState<StepCategory | 'all'>('all');
  const [searchFilter, setSearchFilter] = useState('');

  // Export state
  const [exportAnchorEl, setExportAnchorEl] = useState<null | HTMLElement>(null);
  const [includeData, setIncludeData] = useState(() => {
    return localStorage.getItem(PREF_INCLUDE_DATA) === 'true';
  });

  const handleIncludeDataChange = (checked: boolean) => {
    setIncludeData(checked);
    localStorage.setItem(PREF_INCLUDE_DATA, String(checked));
  };

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
      tables_touched: Array.from(tables).sort(),
    };
  }, [stepsData]);

  const handleExportMd = () => {
    window.location.href = `/api/sessions/${sessionId}/export.md?include_data=${includeData}`;
  };
  const handleExportJson = () => {
    window.location.href = `/api/sessions/${sessionId}/export.json`;
  };
  const handleCopyReport = async () => {
    // If called from card button, use current includeData state
    await handleCopyForPr(includeData);
  };

  const handleCopyForPr = async (withData: boolean) => {
    const res = await receipt.mutateAsync(withData);
    await copyToClipboard(res.markdown);
    setExportAnchorEl(null);
  };

  const handleSaveTag = async (tag: string | null) => {
    await updateTag.mutateAsync(tag);
  };

  const handleSaveRepoRoot = async (repoRoot: string | null) => {
    await updateRepoRoot.mutateAsync(repoRoot);
  };

  // Timeline Step Actions
  const handleCopyStepSql = async (step: ObservedStep) => {
    const sql = extractSqlExcerpt(step);
    if (!sql) return;
    await copyToClipboard(sql);
  };

  const handleCopyStepJson = async (step: ObservedStep) => {
    await copyToClipboard(JSON.stringify(step, null, 2));
  };

  const handleExportStepJson = (step: ObservedStep) => {
    const blob = new Blob([JSON.stringify(step, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `step-${step.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

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
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {session.data && (
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', bgcolor: 'background.default' }}>
          <SessionSummaryCard
            key={`${session.data.id}-${session.data.context?.repo_root ?? ''}-${session.data.context?.tag ?? ''}`}
            session={session.data}
            rollup={rollup.data ?? null}
            isLoading={rollup.isLoading}
            onCopyForPr={handleCopyReport}
            // onExportJson={handleExportJson} // Removed JSON button
            onSaveRepoRoot={handleSaveRepoRoot}
            onSaveTag={handleSaveTag}
            isCopying={receipt.isPending}
            isSavingRepoRoot={updateRepoRoot.isPending}
            isSavingTag={updateTag.isPending}
          />
        </Box>
      )}
      <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
        <EvidenceWorkspace
          step={selectedStep}
          cast={activeCast}
          pendingRequest={activePendingRequest}
          onAllow={(id) => allowPending.mutate(id)}
          onDeny={(id) => denyPending.mutate(id)}
          isDecisionLoading={allowPending.isPending || denyPending.isPending}
        />
      </Box>
    </Box>
  );

  // -- Right Panel (Timeline) --
  const Right = (
    <RightPanel
      headerContent={
        selectedStep ? (
          <Stack
            direction='row'
            alignItems='center'
            justifyContent='space-between'
            sx={{ minHeight: 24 }}
          >
            <Stack direction='row' spacing={1} alignItems='center'>
              <Typography variant='overline' fontWeight={700} color='text.primary'>
                STEP ACTION
              </Typography>
            </Stack>
            <Stack direction='row' spacing={0.5}>
              {extractSqlExcerpt(selectedStep) && (
                <Tooltip title='Copy SQL'>
                  <IconButton size='small' onClick={() => handleCopyStepSql(selectedStep)}>
                    <CodeIcon fontSize='small' />
                  </IconButton>
                </Tooltip>
              )}
              <Tooltip title='Copy Step JSON'>
                <IconButton size='small' onClick={() => handleCopyStepJson(selectedStep)}>
                  <ContentCopyIcon fontSize='small' />
                </IconButton>
              </Tooltip>
              <Tooltip title='Export Step JSON'>
                <IconButton size='small' onClick={() => handleExportStepJson(selectedStep)}>
                  <FileDownloadIcon fontSize='small' />
                </IconButton>
              </Tooltip>
              <Tooltip title='Clear selection'>
                <IconButton size='small' onClick={() => setSelectedStepId(null)}>
                  <CloseIcon fontSize='small' />
                </IconButton>
              </Tooltip>
            </Stack>
          </Stack>
        ) : undefined
      }
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

  return (
    <>
      <DashboardLayout
        headerProps={{
          title: session.data?.title ?? 'Untitled Session',
          steps: stepsData,
          showBack: true,
          actions: (
            <>
              <Button
                variant='outlined'
                size='small'
                endIcon={<KeyboardArrowDownIcon />}
                onClick={(e) => setExportAnchorEl(e.currentTarget)}
                sx={{
                  borderColor: 'divider',
                  color: 'text.secondary',
                  textTransform: 'none',
                  fontWeight: 600,
                }}
              >
                Export
              </Button>
              <Menu
                anchorEl={exportAnchorEl}
                open={Boolean(exportAnchorEl)}
                onClose={() => setExportAnchorEl(null)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                PaperProps={{ sx: { minWidth: 220, mt: 1 } }}
              >
                <MenuItem onClick={() => handleIncludeDataChange(!includeData)}>
                  <ListItemIcon>
                    <Switch
                      size='small'
                      checked={includeData}
                      onChange={(e) => handleIncludeDataChange(e.target.checked)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </ListItemIcon>
                  <ListItemText primary='Include sample data' />
                </MenuItem>

                <Divider />
                <ListSubheader sx={{ lineHeight: '32px' }}>Report</ListSubheader>

                <MenuItem onClick={() => handleCopyForPr(includeData)}>
                  <ListItemIcon>
                    <ContentCopyIcon fontSize='small' />
                  </ListItemIcon>
                  <ListItemText primary='Copy report (Markdown)' />
                </MenuItem>
                <MenuItem
                  onClick={() => {
                    handleExportMd();
                    setExportAnchorEl(null);
                  }}
                >
                  <ListItemIcon>
                    <FileDownloadIcon fontSize='small' />
                  </ListItemIcon>
                  <ListItemText primary='Download report (.md)' />
                </MenuItem>

                <Divider />
                <ListSubheader sx={{ lineHeight: '32px' }}>Data</ListSubheader>

                <MenuItem
                  onClick={() => {
                    handleExportJson();
                    setExportAnchorEl(null);
                  }}
                >
                  <ListItemIcon>
                    <DataObjectIcon fontSize='small' />
                  </ListItemIcon>
                  <ListItemText primary='Download session JSON' />
                </MenuItem>
              </Menu>
            </>
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

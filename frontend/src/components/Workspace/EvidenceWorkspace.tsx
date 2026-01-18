import { Alert, Box, Button, Divider, Stack, Typography } from '@mui/material';
import BlockIcon from '@mui/icons-material/Block';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';

import { StatusBanner } from './StatusBanner';
import { JsonViewer } from '../JsonViewer';

import type { Cast, ObservedStep, PendingRequest } from '../../api/types';
import { CastRenderer } from '../CastRenderer';
import {
  computeStepNarrative,
  extractDatabaseErrorMessage,
  extractSqlExcerpt,
  getStepDecision,
  getStepStatusLabel,
} from '../../utils/stepUtils';

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
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'text.secondary',
          bgcolor: 'background.default',
        }}
      >
        <Typography variant='h6' gutterBottom>
          Select a step to inspect
        </Typography>
        <Typography variant='body2'>
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

  const statusLabel = getStepStatusLabel(step);
  const decision = getStepDecision(step);
  const narrative = computeStepNarrative(step);
  const sqlExcerpt = extractSqlExcerpt(step);
  const errorMessage = extractDatabaseErrorMessage(step);

  const statusColor =
    statusLabel === 'OK' || statusLabel === 'ALLOWED'
      ? 'success.main'
      : statusLabel === 'ERROR' || statusLabel === 'DENIED'
        ? 'error.main'
        : 'warning.main';

  const copySql = () => {
    if (!sqlExcerpt) return;
    navigator.clipboard.writeText(sqlExcerpt);
  };

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.default',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 3,
          py: 2,
          borderBottom: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <Stack spacing={0.5}>
          {/* Metadata Bar: NAME • STATUS • TIME • DURATION */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              color: 'text.secondary',
              fontSize: '0.75rem',
              fontFamily: 'monospace',
            }}
          >
            <Typography
              variant='inherit'
              component='span'
              fontWeight={700}
              sx={{ color: 'primary.main' }}
            >
              {step.name.toUpperCase()}
            </Typography>

            <span>•</span>

            <Typography
              variant='inherit'
              component='span'
              sx={{
                color: statusColor,
                fontWeight: 600,
              }}
            >
              {statusLabel}
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
              size='small'
              onClick={copyEvidence}
              sx={{
                color: 'text.secondary',
                minWidth: 'auto',
                px: 1,
                textTransform: 'none',
              }}
            >
              JSON
            </Button>
          </Box>

          {/* Main Narrative Title */}
          <Typography variant='h6' fontWeight={600} sx={{ lineHeight: 1.3 }}>
            {step.summary || narrative}
          </Typography>
        </Stack>
      </Box>

      {/* Scrollable Content */}
      <Box sx={{ flexGrow: 1, overflow: 'auto', p: 3 }}>
        <Stack spacing={4}>
          {/* Blocker Action Area */}
          {(step.kind === 'blocker' || step.kind === 'blocker_decision' || pendingRequest) && (
            <StatusBanner
              variant={
                statusLabel === 'ALLOWED'
                  ? 'success'
                  : statusLabel === 'DENIED'
                    ? 'error'
                    : 'warning'
              }
              icon={
                statusLabel === 'ALLOWED' ? (
                  <CheckCircleIcon />
                ) : statusLabel === 'DENIED' ? (
                  <BlockIcon />
                ) : (
                  <WarningAmberIcon />
                )
              }
              title={
                statusLabel === 'ALLOWED'
                  ? 'Action Allowed'
                  : statusLabel === 'DENIED'
                    ? 'Action Denied'
                    : 'Action Blocked'
              }
              description={
                pendingRequest?.reason || step.summary || 'This action requires approval.'
              }
            >
              {pendingRequest && pendingRequest.status === 'pending' && (
                <Stack direction='row' spacing={2}>
                  <Button
                    variant='outlined'
                    color='success'
                    size='small'
                    startIcon={<PlayArrowIcon />}
                    onClick={() => onAllow?.(pendingRequest.id)}
                    disabled={isDecisionLoading}
                    sx={{
                      bgcolor: 'background.paper',
                      '&:hover': { bgcolor: 'success.dark', color: 'white' },
                    }}
                  >
                    Allow
                  </Button>
                  <Button
                    variant='outlined'
                    color='error'
                    size='small'
                    startIcon={<StopIcon />}
                    onClick={() => onDeny?.(pendingRequest.id)}
                    disabled={isDecisionLoading}
                    sx={{
                      bgcolor: 'background.paper',
                      '&:hover': { bgcolor: 'error.dark', color: 'white' },
                    }}
                  >
                    Deny
                  </Button>
                </Stack>
              )}
              {pendingRequest && pendingRequest.status !== 'pending' && (
                <Alert
                  severity={pendingRequest.status === 'allowed' ? 'success' : 'error'}
                  sx={{
                    bgcolor: 'background.paper',
                    border: 1,
                    borderColor: 'divider',
                  }}
                >
                  Decision: {pendingRequest.status.toUpperCase()}
                </Alert>
              )}
              {!pendingRequest && decision && (
                <Alert
                  severity={
                    decision === 'allowed' ? 'success' : decision === 'denied' ? 'error' : 'warning'
                  }
                  sx={{
                    bgcolor: 'background.paper',
                    border: 1,
                    borderColor: 'divider',
                  }}
                >
                  Decision: {decision.toUpperCase()}
                </Alert>
              )}
            </StatusBanner>
          )}

          {/* CAST (Visual Artifact) */}
          {cast && (
            <Box>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  mb: 1,
                }}
              >
                <Typography variant='overline' color='text.secondary' fontWeight={700}>
                  ARTIFACT
                </Typography>
                <Button
                  size='small'
                  variant='outlined'
                  onClick={() => {
                    window.location.href = `/api/casts/${cast.id}/export.md`;
                  }}
                  sx={{ textTransform: 'none', borderColor: 'divider', color: 'text.secondary' }}
                >
                  Export Artifact Receipt
                </Button>
              </Box>
              <CastRenderer cast={cast} />
            </Box>
          )}

          {/* TRACE (Request / Policy / Response) */}
          <Box>
            <Typography
              variant='overline'
              color='text.secondary'
              fontWeight={700}
              sx={{ mb: 1, display: 'block' }}
            >
              TRACE
            </Typography>
            <Stack spacing={2}>
              <Box
                sx={{
                  p: 2,
                  bgcolor: 'background.paper',
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                }}
              >
                <Typography
                  variant='caption'
                  fontWeight={700}
                  color='text.secondary'
                  fontFamily='monospace'
                >
                  REQUEST
                </Typography>
                <Stack spacing={0.5} sx={{ mt: 1, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                  {step.target_type && (
                    <Typography variant='inherit'>target: {step.target_type}</Typography>
                  )}
                  {step.tool_category && (
                    <Typography variant='inherit'>category: {step.tool_category}</Typography>
                  )}
                  <Typography variant='inherit'>tool: {step.name}</Typography>
                  {sqlExcerpt && (
                    <Box>
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <Typography variant='inherit'>sql:</Typography>
                        <Button
                          size='small'
                          startIcon={<ContentCopyIcon />}
                          onClick={copySql}
                          sx={{ textTransform: 'none', color: 'text.secondary' }}
                        >
                          Copy
                        </Button>
                      </Box>
                      <Box
                        sx={{
                          mt: 1,
                          p: 1,
                          bgcolor: 'background.default',
                          border: 1,
                          borderColor: 'divider',
                          borderRadius: 1,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          maxHeight: 200,
                          overflow: 'auto',
                        }}
                      >
                        {sqlExcerpt}
                      </Box>
                    </Box>
                  )}
                </Stack>
              </Box>

              <Box
                sx={{
                  p: 2,
                  bgcolor: 'background.paper',
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                }}
              >
                <Typography
                  variant='caption'
                  fontWeight={700}
                  color='text.secondary'
                  fontFamily='monospace'
                >
                  POLICY
                </Typography>
                <Stack spacing={0.5} sx={{ mt: 1, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                  {step.sql_classification && (
                    <Typography variant='inherit'>
                      classification: {step.sql_classification}
                    </Typography>
                  )}
                  {step.risk_level && (
                    <Typography variant='inherit'>risk: {step.risk_level}</Typography>
                  )}
                  {step.warnings && step.warnings.length > 0 && (
                    <Typography variant='inherit'>warnings: {step.warnings.join(', ')}</Typography>
                  )}
                  {step.policy_rule_ids && step.policy_rule_ids.length > 0 && (
                    <Typography variant='inherit'>
                      rules: {step.policy_rule_ids.join(', ')}
                    </Typography>
                  )}
                  {decision && <Typography variant='inherit'>decision: {decision}</Typography>}
                </Stack>
              </Box>

              <Box
                sx={{
                  p: 2,
                  bgcolor: 'background.paper',
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                }}
              >
                <Typography
                  variant='caption'
                  fontWeight={700}
                  color='text.secondary'
                  fontFamily='monospace'
                >
                  RESPONSE
                </Typography>
                <Stack spacing={0.5} sx={{ mt: 1, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                  {typeof step.duration_ms === 'number' && (
                    <Typography variant='inherit'>duration_ms: {step.duration_ms}</Typography>
                  )}
                  {typeof step.result_rows_shown === 'number' && (
                    <Typography variant='inherit'>rows_shown: {step.result_rows_shown}</Typography>
                  )}
                  {typeof step.result_rows_total === 'number' && (
                    <Typography variant='inherit'>rows_total: {step.result_rows_total}</Typography>
                  )}
                  {typeof step.captured_bytes === 'number' && (
                    <Typography variant='inherit'>captured_bytes: {step.captured_bytes}</Typography>
                  )}
                  {errorMessage && <Typography variant='inherit'>error: {errorMessage}</Typography>}
                </Stack>
              </Box>
            </Stack>
          </Box>

          {/* EVIDENCE (Input/Output) */}
          <Divider sx={{ my: 1, opacity: 0.5 }} />
          <Typography
            variant='overline'
            color='text.secondary'
            fontWeight={700}
            sx={{ mb: 1, display: 'block' }}
          >
            EVIDENCE
          </Typography>

          <Stack spacing={2}>
            <JsonViewer label='INPUT (ARGS)' data={step.args} />
            {step.result != null && <JsonViewer label='RESULT' data={step.result} />}
          </Stack>
        </Stack>
      </Box>
    </Box>
  );
}

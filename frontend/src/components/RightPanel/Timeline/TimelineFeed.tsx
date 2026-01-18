import {
  Box,
  Chip,
  Divider,
  List,
  ListItemButton,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import BlockIcon from '@mui/icons-material/Block';
import { useMemo, type ReactNode } from 'react';
import type { ObservedStep } from '../../../api/types';

import {
  computeStepNarrative,
  getStepCategory,
  getStepPhase,
  getStepStatusLabel,
  type StepPhase,
} from '../../../utils/stepUtils';

interface TimelineFeedProps {
  steps: ObservedStep[];
  selectedStepId?: string;
  onStepSelect: (stepId: string) => void;
  showPhaseGroups?: boolean;
}

function getPhaseLabel(phase: StepPhase): string {
  if (phase === 'exploration') return 'Exploration';
  if (phase === 'analysis') return 'Analysis';
  if (phase === 'mutation') return 'Attempted mutation';
  if (phase === 'cast') return 'Artifacts';
  return 'Other';
}

type TimelineItem = { kind: 'header'; phase: StepPhase } | { kind: 'step'; step: ObservedStep };

export function TimelineFeed({
  steps,
  selectedStepId,
  onStepSelect,
  showPhaseGroups = true,
}: TimelineFeedProps) {
  const theme = useTheme();

  const items = useMemo<TimelineItem[]>(() => {
    if (!showPhaseGroups) return steps.map((step) => ({ kind: 'step', step }));

    const grouped: TimelineItem[] = [];
    let lastPhase: StepPhase | null = null;
    for (const step of steps) {
      const phase = getStepPhase(step);
      if (phase !== lastPhase) {
        grouped.push({ kind: 'header', phase });
        lastPhase = phase;
      }
      grouped.push({ kind: 'step', step });
    }
    return grouped;
  }, [steps, showPhaseGroups]);

  return (
    <List sx={{ p: 0, width: '100%', bgcolor: 'background.paper' }}>
      {items.map((item, idx) => {
        if (item.kind === 'header') {
          return (
            <Box
              key={`phase-${item.phase}-${idx}`}
              sx={{
                px: 2,
                py: 1,
                bgcolor: 'background.default',
                borderBottom: 1,
                borderColor: theme.palette.divider,
              }}
            >
              <Typography
                variant='overline'
                color='text.secondary'
                fontWeight={800}
                sx={{ fontSize: '0.7rem' }}
              >
                {getPhaseLabel(item.phase)}
              </Typography>
            </Box>
          );
        }

        const step = item.step;
        const isSelected = selectedStepId === step.id;
        const narrative = computeStepNarrative(step);
        const statusLabel = getStepStatusLabel(step);
        const category = getStepCategory(step);

        let StatusIcon = CheckCircleIcon;
        let statusColor = theme.palette.success.main;
        let statusBadge: ReactNode = null;

        if (statusLabel === 'ERROR') {
          StatusIcon = ErrorIcon;
          statusColor = theme.palette.error.main;
        } else if (statusLabel === 'BLOCKED') {
          StatusIcon = BlockIcon;
          statusColor = theme.palette.warning.main;
          statusBadge = (
            <Chip
              label='BLOCKED'
              color='warning'
              size='small'
              sx={{ height: 18, fontSize: '0.65rem', fontWeight: 700 }}
            />
          );
        } else if (statusLabel === 'DENIED') {
          StatusIcon = BlockIcon;
          statusColor = theme.palette.error.main;
          statusBadge = (
            <Chip
              label='DENIED'
              color='error'
              size='small'
              sx={{ height: 18, fontSize: '0.65rem', fontWeight: 700 }}
            />
          );
        } else if (statusLabel === 'TIMEOUT') {
          StatusIcon = BlockIcon;
          statusColor = theme.palette.warning.main;
          statusBadge = (
            <Chip
              label='TIMEOUT'
              color='warning'
              size='small'
              sx={{ height: 18, fontSize: '0.65rem', fontWeight: 700 }}
            />
          );
        } else if (statusLabel === 'ALLOWED') {
          StatusIcon = CheckCircleIcon;
          statusColor = theme.palette.success.main;
          statusBadge = (
            <Chip
              label='ALLOWED'
              color='success'
              size='small'
              sx={{ height: 18, fontSize: '0.65rem', fontWeight: 700 }}
            />
          );
        }

        return (
          <Box key={step.id}>
            <ListItemButton
              selected={isSelected}
              onClick={() => onStepSelect(step.id)}
              sx={{
                borderLeft: 3,
                borderLeftColor: isSelected ? theme.palette.primary.main : 'transparent',
                px: 2,
                py: 1.5,
                alignItems: 'flex-start',
                transition: 'all 0.2s',
                '&.Mui-selected': {
                  bgcolor: 'action.selected',
                  borderLeftColor: theme.palette.primary.main,
                },
              }}
            >
              <Box sx={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 0.5 }}>
                  <StatusIcon
                    sx={{
                      fontSize: 16,
                      color: statusColor,
                      mr: 1,
                      mt: 0.3,
                      flexShrink: 0,
                    }}
                  />

                  <Typography
                    variant='body2'
                    sx={{
                      fontWeight: isSelected ? 600 : 500,
                      flexGrow: 1,
                      lineHeight: 1.4,
                      fontSize: '0.9rem',
                    }}
                  >
                    {narrative}
                  </Typography>
                </Box>

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 3 }}>
                  {/* Tool Name Chip (Secondary) */}
                  <Typography
                    variant='caption'
                    fontFamily='monospace'
                    color='text.secondary'
                    sx={{ fontSize: '0.75rem' }}
                  >
                    {category}:{step.name}
                  </Typography>

                  {statusBadge}

                  {step.warnings && step.warnings.length > 0 && (
                    <Tooltip title={step.warnings.join('\n')}>
                      <Chip
                        label={`${step.warnings.length} warn`}
                        color='warning'
                        size='small'
                        variant='outlined'
                        sx={{ height: 18, fontSize: '0.65rem' }}
                      />
                    </Tooltip>
                  )}

                  <Typography
                    variant='caption'
                    color='text.secondary'
                    sx={{
                      fontSize: '0.75rem',
                      fontFamily: 'monospace',
                      ml: 'auto',
                    }}
                  >
                    {new Date(step.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })}
                  </Typography>
                </Box>
              </Box>
            </ListItemButton>
            <Divider component='li' sx={{ borderColor: theme.palette.divider, opacity: 0.5 }} />
          </Box>
        );
      })}
    </List>
  );
}

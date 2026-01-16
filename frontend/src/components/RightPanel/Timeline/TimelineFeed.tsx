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
import type { ObservedStep } from '../../../api/types';

interface TimelineFeedProps {
  steps: ObservedStep[];
  selectedStepId?: string;
  onStepSelect: (stepId: string) => void;
}

import { computeStepNarrative } from '../../../utils/stepUtils';

export function TimelineFeed({ steps, selectedStepId, onStepSelect }: TimelineFeedProps) {
  const theme = useTheme();

  return (
    <List sx={{ p: 0, width: '100%', bgcolor: 'background.paper' }}>
      {steps.map((step) => {
        const isSelected = selectedStepId === step.id;
        const narrative = computeStepNarrative(step);
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const args = step.args as any;

        // Status Logic
        let StatusIcon = CheckCircleIcon;
        let statusColor = theme.palette.success.main;
        let statusBadge = null;

        if (step.kind === 'blocker') {
          const decision = args?.decision;

          if (!decision) {
            // Pending decision
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
          } else if (decision === 'denied' || decision === 'timeout') {
            // Denied
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
          } else if (decision === 'allowed') {
            // Allowed
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
        } else if (step.status === 'error') {
          StatusIcon = ErrorIcon;
          statusColor = theme.palette.error.main;
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
                    {step.name}
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

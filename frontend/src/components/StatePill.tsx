import { Chip, keyframes, styled } from '@mui/material';
import type { ObservedStep } from '../api/types';

export type SessionState = 'THINKING' | 'QUERYING' | 'FETCHING' | 'DONE' | 'BLOCKED' | 'ERROR';

function deriveState(steps: ObservedStep[]): SessionState {
  if (steps.length === 0) return 'THINKING';
  const last = steps[steps.length - 1];

  if (last.status === 'error') return 'ERROR';
  if (last.kind === 'blocker') return 'BLOCKED';
  // If the last step is "running" (which we might infer if we had a running flag,
  // but for now we look at the type of the last event.
  // v0 simplification: if it's the very last event in the stream, assume it's valid state)

  // TODO: Add "isStreaming" check if available from parent, for now purely last-event based
  if (last.name === 'query') return 'QUERYING';
  if (last.name === 'list_tables' || last.name === 'describe_table') return 'FETCHING';

  return 'DONE';
}

const pulse = keyframes`
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(0.95); }
  100% { opacity: 1; transform: scale(1); }
`;

const AnimatedChip = styled(Chip, {
  shouldForwardProp: (prop) => prop !== 'isPulsing',
})<{ isPulsing?: boolean }>(({ isPulsing }) => ({
  fontWeight: 600,
  minWidth: 80,
  ...(isPulsing && {
    animation: `${pulse} 1.5s infinite ease-in-out`,
  }),
}));

export function StatePill(props: { steps: ObservedStep[] }) {
  const state = deriveState(props.steps);

  let color: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' =
    'default';
  let isPulsing = false;

  switch (state) {
    case 'THINKING':
      color = 'info';
      isPulsing = true;
      break;
    case 'QUERYING':
    case 'FETCHING':
      color = 'secondary';
      isPulsing = true;
      break;
    case 'BLOCKED':
      color = 'warning';
      isPulsing = true;
      break;
    case 'ERROR':
      color = 'error';
      break;
    case 'DONE':
      color = 'success';
      break;
  }

  return (
    <AnimatedChip
      label={state}
      color={color}
      size='small'
      isPulsing={isPulsing}
      variant={state === 'DONE' ? 'outlined' : 'filled'}
      sx={{
        ...(state === 'DONE'
          ? {
              fontWeight: 700,
              borderWidth: 1,
              borderColor: '#238636',
              color: '#3fb950',
              bgcolor: 'transparent',
              '& .MuiChip-label': { px: 1 },
            }
          : {}),
      }}
    />
  );
}

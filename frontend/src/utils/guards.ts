import type { BlockerDecisionArgs } from '../api/types';

export function isBlockerDecisionArgs(args: unknown): args is BlockerDecisionArgs {
  if (typeof args !== 'object' || args === null) {
    return false;
  }
  const a = args as Record<string, unknown>;
  return (
    (a.decision === 'allowed' || a.decision === 'denied') &&
    (typeof a.reason === 'string' || a.reason === undefined)
  );
}

import { ObservedStep } from '../api/types';

export function findDatabaseErrorInValue(value: unknown): string | null {
  if (typeof value === 'string') return findDatabaseErrorInText(value);

  if (Array.isArray(value)) {
    for (const item of value) {
      const message = findDatabaseErrorInValue(item);
      if (message) return message;
    }
    return null;
  }

  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    const textValue = record.text;
    if (typeof textValue === 'string') {
      const message = findDatabaseErrorInText(textValue);
      if (message) return message;
    }
  }

  return null;
}

export function findDatabaseErrorInText(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed) return null;

  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      const parsed = JSON.parse(trimmed) as unknown;
      return findDatabaseErrorInValue(parsed);
    } catch {
      return null;
    }
  }

  if (trimmed.toLowerCase().startsWith('database error')) return trimmed;
  return null;
}

export function extractDatabaseErrorMessage(step: ObservedStep): string | null {
  if (step.status !== 'error') return null;
  const raw = findDatabaseErrorInValue(step.result);
  if (!raw) return null;
  return raw.replace(/^Database error:\s*/i, '').trim();
}

export function computeStepNarrative(step: ObservedStep): string {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const args = step.args as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const result = step.result as any;

  if (step.kind === 'blocker') {
    const decision = args?.decision;
    const reason = args?.reason || step.summary || 'Action Blocked';

    // If decision is present, show the final state
    if (decision === 'allowed') return `Allowed: ${reason}`;
    if (decision === 'denied') return `Denied: ${reason}`;
    if (decision === 'timeout') return `Timed out: ${reason}`;

    // Otherwise, still pending
    return `Blocked: ${reason}`;
  }

  const dbErrorMessage = extractDatabaseErrorMessage(step);
  if (step.status === 'error') {
    const duration = step.duration_ms ? `${step.duration_ms}ms` : '';
    const base = step.name === 'query' ? 'Query failed' : `${step.name} failed`;
    const suffix = dbErrorMessage ? ` — ${dbErrorMessage}` : '';
    return `${base}${duration ? ` (${duration})` : ''}${suffix}`;
  }

  if (step.name === 'query') {
    // Try to find table name in SQL (heuristic) or just use logic
    const sql = args?.sql || '';
    const tableName = sql.match(/FROM\s+([a-zA-Z0-9_]+)/i)?.[1] || 'query';

    let meta = '';
    if (result && Array.isArray(result)) {
      meta = `${result.length} rows`;
    } else if (result?.rows_shown !== undefined) {
      // Handle cast_table result format if query result mimics it or if result is cap object
      meta = `${result.total_rows ?? 'unknown'} rows`;
    } else if (step.preview?.text) {
      // Fallback to estimating from preview if result is opaque
      meta = 'result ready';
    }

    const duration = step.duration_ms ? `${step.duration_ms}ms` : '';
    return `Query: ${tableName} (${[meta, duration].filter(Boolean).join('; ')})`;
  }

  if (step.name === 'cast_table') {
    const title = args?.title || 'Table';
    const rows = result?.total_rows ?? result?.rows_shown ?? 'unknown';
    return `Cast table: ${title} (${rows} rows)`;
  }

  // Default fallback
  return step.summary || step.name;
}

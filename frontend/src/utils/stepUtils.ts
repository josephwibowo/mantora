import type { ObservedStep, StepCategory, StepDecision } from '../api/types';

export type StepStatusLabel = 'OK' | 'ERROR' | 'BLOCKED' | 'ALLOWED' | 'DENIED' | 'TIMEOUT';
export type StepPhase = 'exploration' | 'analysis' | 'mutation' | 'cast' | 'other';

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

export function getStepArgs(step: ObservedStep): UnknownRecord | null {
  return isRecord(step.args) ? step.args : null;
}

export function getStepDecision(step: ObservedStep): StepDecision | null {
  if (step.decision) return step.decision;
  const args = getStepArgs(step);
  const value = args?.decision;
  if (value === 'pending' || value === 'allowed' || value === 'denied' || value === 'timeout')
    return value;
  return null;
}

export function getStepStatusLabel(step: ObservedStep): StepStatusLabel {
  if (step.kind === 'blocker' || step.kind === 'blocker_decision') {
    const decision = getStepDecision(step);
    if (!decision || decision === 'pending') return 'BLOCKED';
    if (decision === 'allowed') return 'ALLOWED';
    if (decision === 'timeout') return 'TIMEOUT';
    return 'DENIED';
  }
  return step.status === 'error' ? 'ERROR' : 'OK';
}

export function getStepCategory(step: ObservedStep): StepCategory {
  if (step.tool_category) return step.tool_category;
  if (step.name.startsWith('cast_') || step.name === 'cast_table') return 'cast';
  if (step.name === 'query' || step.name === 'execute') return 'query';
  return 'unknown';
}

export function extractSqlExcerpt(step: ObservedStep): string | null {
  if (step.sql?.text) return step.sql.text;
  const args = getStepArgs(step);
  const sql = args?.sql;
  return typeof sql === 'string' ? sql : null;
}

export function extractTableTouched(step: ObservedStep): string | null {
  const sql = extractSqlExcerpt(step);
  if (!sql) return null;
  const match = sql.match(/\\bFROM\\s+([a-zA-Z0-9_\\.]+)/i);
  return match?.[1] ?? null;
}

export function getStepPhase(step: ObservedStep): StepPhase {
  const category = getStepCategory(step);
  if (category === 'cast') return 'cast';
  if (category === 'schema' || category === 'list') return 'exploration';
  if (category === 'query') {
    const warnings = step.warnings ?? [];
    const isMutationish =
      (step.risk_level ?? '').toUpperCase() === 'CRITICAL' ||
      warnings.includes('DDL') ||
      warnings.includes('DML') ||
      getStepStatusLabel(step) !== 'OK';
    return isMutationish ? 'mutation' : 'analysis';
  }
  if (getStepStatusLabel(step) !== 'OK') return 'mutation';
  return 'other';
}

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
  if (step.error_message) return step.error_message;
  if (step.status !== 'error') return null;
  const raw = findDatabaseErrorInValue(step.result);
  if (!raw) return null;
  return raw.replace(/^Database error:\s*/i, '').trim();
}

export function computeStepNarrative(step: ObservedStep): string {
  const args = getStepArgs(step);
  const result = isRecord(step.result) ? step.result : null;
  const status = getStepStatusLabel(step);

  if (step.kind === 'blocker' || step.kind === 'blocker_decision') {
    const reason =
      (typeof args?.reason === 'string' ? args.reason : null) || step.summary || 'Action';

    // If decision is present, show the final state
    if (status === 'ALLOWED') return `Allowed: ${reason}`;
    if (status === 'DENIED') return `Denied: ${reason}`;
    if (status === 'TIMEOUT') return `Timed out: ${reason}`;
    return `Blocked: ${reason}`;
  }

  const dbErrorMessage = extractDatabaseErrorMessage(step);
  if (status === 'ERROR') {
    const duration = step.duration_ms ? `${step.duration_ms}ms` : '';
    const base = step.name === 'query' ? 'Query failed' : `${step.name} failed`;
    const suffix = dbErrorMessage ? ` — ${dbErrorMessage}` : '';
    return `${base}${duration ? ` (${duration})` : ''}${suffix}`;
  }

  if (getStepCategory(step) === 'query') {
    // Try to find table name in SQL (heuristic) or just use logic
    const tableName = extractTableTouched(step) || 'query';

    let meta = '';
    if (typeof step.result_rows_total === 'number') meta = `${step.result_rows_total} rows`;
    else if (typeof step.result_rows_shown === 'number') meta = `${step.result_rows_shown} rows`;
    else if (step.preview?.text) meta = 'result ready';

    const duration = step.duration_ms ? `${step.duration_ms}ms` : '';
    return `Query: ${tableName} (${[meta, duration].filter(Boolean).join('; ')})`;
  }

  if (getStepCategory(step) === 'cast') {
    const title = typeof args?.title === 'string' ? args.title : 'Table';
    const rows =
      typeof step.result_rows_total === 'number'
        ? step.result_rows_total
        : typeof step.result_rows_shown === 'number'
          ? step.result_rows_shown
          : typeof result?.total_rows === 'number'
            ? result.total_rows
            : typeof result?.rows_shown === 'number'
              ? result.rows_shown
              : 'unknown';
    return `Cast table: ${title} (${rows} rows)`;
  }

  // Default fallback
  return step.summary || step.name;
}

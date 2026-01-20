export type TruncatedText = {
  text: string;
  truncated: boolean;
};

export type StepCategory = 'query' | 'schema' | 'list' | 'cast' | 'unknown';
export type StepDecision = 'pending' | 'allowed' | 'denied' | 'timeout';

export type SessionContext = {
  repo_root?: string | null;
  repo_name?: string | null;
  branch?: string | null;
  commit?: string | null;
  dirty?: boolean | null;
  config_source?: 'cli' | 'env' | 'pinned' | 'roots' | 'ui' | 'git' | 'unknown';
  tag?: string | null;
};

export type Session = {
  id: string;
  title: string | null;
  created_at: string;
  context?: SessionContext | null;
};

export type ObservedStep = {
  id: string;
  session_id: string;
  created_at: string;

  kind: 'tool_call' | 'tool_result' | 'note' | 'blocker' | 'blocker_decision';
  name: string;

  status: 'ok' | 'error';
  duration_ms: number | null;

  summary?: string | null;
  risk_level?: string | null;
  warnings?: string[] | null;
  tables_touched?: string[] | null;

  // Receipt/trace v1 (optional for backwards compatibility)
  target_type?: string | null;
  tool_category?: StepCategory | null;
  sql?: TruncatedText | null;
  sql_classification?: string | null;
  policy_rule_ids?: string[] | null;
  decision?: StepDecision | null;
  result_rows_shown?: number | null;
  result_rows_total?: number | null;
  captured_bytes?: number | null;
  error_message?: string | null;

  args: unknown | null;
  result: unknown | null;

  preview: TruncatedText | null;
};

export type PendingRequestStatus = 'pending' | 'allowed' | 'denied' | 'timeout';

export type PendingRequest = {
  id: string;
  session_id: string;
  created_at: string;

  tool_name: string;
  arguments: unknown;

  classification: string | null;
  risk_level: string | null;
  reason: string | null;

  blocker_step_id: string | null;

  status: PendingRequestStatus;
  decided_at: string | null;
};

export type CastKind = 'table';

export type Cast = {
  id: string;
  session_id: string;
  created_at: string;
  kind: CastKind;
  title: string;
  origin_step_id: string;
  origin_step_ids: string[];

  // Table-specific
  sql?: string;
  rows?: Record<string, unknown>[];
  total_rows?: number;
  columns?: { name: string; type: string | null }[] | null;

  truncated: boolean;
};

export type SessionSummary = {
  tool_calls: number;
  queries: number;
  casts: number;
  blocks: number;
  errors: number;
  warnings: number;
  approvals?: number;
  duration_ms_total?: number | null;
  status?: 'clean' | 'warnings' | 'blocked' | null;
  tables_touched?: string[] | null;
};

export type ReceiptResult = {
  markdown: string;
  truncated: boolean;
  included_data: boolean;
  format: 'gfm' | 'plain';
};

export type PolicyRule = {
  id: string;
  label: string;
  description: string;
};

export type PolicyManifest = {
  safety_mode: 'protective' | 'transparent';
  active_rules: PolicyRule[];
  limits: {
    max_preview_rows: number;
    max_preview_payload_bytes: number;
    max_columns: number;
  };
};

export type BlockerDecisionArgs = {
  decision: 'allowed' | 'denied';
  reason?: string;
  user_id?: string;
};

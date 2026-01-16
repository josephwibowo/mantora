export type TruncatedText = {
  text: string;
  truncated: boolean;
};

export type Session = {
  id: string;
  title: string | null;
  created_at: string;
};

export type ObservedStep = {
  id: string;
  session_id: string;
  created_at: string;

  kind: "tool_call" | "tool_result" | "note" | "blocker" | "blocker_decision";
  name: string;

  status: "ok" | "error";
  duration_ms: number | null;

  summary?: string | null;
  risk_level?: string | null;
  warnings?: string[] | null;

  args: unknown;
  result: unknown;

  preview: TruncatedText | null;
};

export type PendingRequestStatus = "pending" | "allowed" | "denied" | "timeout";

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

export type CastKind = "table";

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
};

export type PolicyRule = {
  id: string;
  label: string;
  description: string;
};

export type PolicyManifest = {
  safety_mode: "protective" | "transparent";
  active_rules: PolicyRule[];
  limits: {
    max_preview_rows: number;
    max_preview_payload_bytes: number;
    max_columns: number;
  };
};

export type BlockerDecisionArgs = {
  decision: "allowed" | "denied";
  reason?: string;
  user_id?: string;
};

import { type UseQueryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from './client';
import type {
  Cast,
  ObservedStep,
  PendingRequest,
  PolicyManifest,
  ReceiptResult,
  Session,
  SessionSummary,
} from './types';

export interface SessionsFilterParams {
  q?: string;
  tag?: string;
  repo_name?: string;
  branch?: string;
  since?: string;
  has_warnings?: boolean;
  has_blocks?: boolean;
}

function buildQueryParams(params: SessionsFilterParams | undefined): string {
  if (!params) return '';
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.tag) qs.set('tag', params.tag);
  if (params.repo_name) qs.set('repo_name', params.repo_name);
  if (params.branch) qs.set('branch', params.branch);
  if (params.since) qs.set('since', params.since);
  if (params.has_warnings !== undefined) qs.set('has_warnings', String(params.has_warnings));
  if (params.has_blocks !== undefined) qs.set('has_blocks', String(params.has_blocks));
  const rendered = qs.toString();
  return rendered ? `?${rendered}` : '';
}

export function useSessions(params?: SessionsFilterParams) {
  const qs = buildQueryParams(params);
  return useQuery({
    queryKey: ['sessions', qs],
    queryFn: () => apiFetch<Session[]>(`/api/sessions${qs}`),
    refetchInterval: 1000,
  });
}

export function useSession(sessionId: string) {
  return useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => apiFetch<Session>(`/api/sessions/${sessionId}`),
    enabled: Boolean(sessionId),
  });
}

export function useSteps(
  sessionId: string,
  options?: Omit<UseQueryOptions<ObservedStep[]>, 'queryKey' | 'queryFn'>,
) {
  return useQuery({
    queryKey: ['steps', sessionId],
    queryFn: () => apiFetch<ObservedStep[]>(`/api/sessions/${sessionId}/steps`),
    enabled: Boolean(sessionId),
    refetchInterval: 1000,
    ...options,
  });
}

export function useCasts(
  sessionId: string,
  options?: Omit<UseQueryOptions<Cast[]>, 'queryKey' | 'queryFn'>,
) {
  return useQuery({
    queryKey: ['casts', sessionId],
    queryFn: () => apiFetch<Cast[]>(`/api/sessions/${sessionId}/casts`),
    enabled: Boolean(sessionId),
    refetchInterval: 1000,
    ...options,
  });
}

export function useCast(castId: string) {
  return useQuery({
    queryKey: ['cast', castId],
    queryFn: () => apiFetch<Cast>(`/api/casts/${castId}`),
    enabled: Boolean(castId),
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (title: string | null) => {
      const res = await apiFetch<{ session: Session }>('/api/sessions', {
        method: 'POST',
        body: JSON.stringify({ title }),
      });
      return res.session;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
}

export function useDeleteSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (sessionId: string) => {
      await apiFetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
}

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: () => apiFetch<PolicyManifest>('/api/settings'),
    staleTime: Infinity, // Settings are static at runtime
  });
}

export function useSessionsSummaries(sessionIds: string[]) {
  const idsKey = [...sessionIds].sort().join('|');
  return useQuery({
    queryKey: ['sessionsSummaries', idsKey],
    queryFn: async () => {
      const entries = await Promise.all(
        [...sessionIds].map(async (id) => {
          const summary = await apiFetch<SessionSummary>(`/api/sessions/${id}/summary`);
          return [id, summary] as const;
        }),
      );
      return Object.fromEntries(entries) as Record<string, SessionSummary>;
    },
    enabled: sessionIds.length > 0,
    refetchInterval: 5000,
  });
}

export function useSessionRollup(sessionId: string) {
  return useQuery({
    queryKey: ['rollup', sessionId],
    queryFn: () => apiFetch<SessionSummary>(`/api/sessions/${sessionId}/rollup`),
    enabled: Boolean(sessionId),
    refetchInterval: 5000,
  });
}

export function useSessionReceipt(sessionId: string) {
  type ReceiptParams = { includeData: boolean; format?: 'gfm' | 'plain' };

  return useMutation({
    mutationFn: ({ includeData, format = 'gfm' }: ReceiptParams) =>
      apiFetch<ReceiptResult>(`/api/sessions/${sessionId}/receipt`, {
        method: 'POST',
        body: JSON.stringify({ include_data: includeData, format }),
        headers: { 'Content-Type': 'application/json' },
      }),
  });
}

export function useUpdateSessionTag(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (tag: string | null) => {
      return apiFetch<Session>(`/api/sessions/${sessionId}`, {
        method: 'PATCH',
        body: JSON.stringify({ tag }),
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
      await queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
}

export function useUpdateSessionRepoRoot(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (repoRoot: string | null) => {
      return apiFetch<Session>(`/api/sessions/${sessionId}/repo-root`, {
        method: 'PUT',
        body: JSON.stringify({ repo_root: repoRoot }),
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
      await queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
}

export function usePendingRequests(
  sessionId: string,
  options?: Omit<UseQueryOptions<PendingRequest[]>, 'queryKey' | 'queryFn'>,
) {
  return useQuery({
    queryKey: ['pending', sessionId],
    queryFn: () => apiFetch<PendingRequest[]>(`/api/sessions/${sessionId}/pending`),
    enabled: Boolean(sessionId),
    refetchInterval: 1000,
    ...options,
  });
}

export function useAllowPending(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (requestId: string) => {
      return apiFetch<PendingRequest>(`/api/pending/${requestId}/allow`, {
        method: 'POST',
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['pending', sessionId] });
      await queryClient.invalidateQueries({ queryKey: ['steps', sessionId] });
    },
  });
}

export function useDenyPending(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (requestId: string) => {
      return apiFetch<PendingRequest>(`/api/pending/${requestId}/deny`, {
        method: 'POST',
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['pending', sessionId] });
      await queryClient.invalidateQueries({ queryKey: ['steps', sessionId] });
    },
  });
}

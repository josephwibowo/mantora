import { type UseQueryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from './client';
import type { Cast, ObservedStep, PendingRequest, PolicyManifest, Session } from './types';

export function useSessions() {
  return useQuery({
    queryKey: ['sessions'],
    queryFn: () => apiFetch<Session[]>('/api/sessions'),
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

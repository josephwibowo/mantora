import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, type Mock } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SessionsPage } from '../SessionsPage';
import * as Queries from '../../api/queries';

// Mock the API hooks
vi.mock('../../api/queries', async () => {
  const actual = await vi.importActual('../../api/queries');
  return {
    ...actual,
    useSessions: vi.fn(),
    useCreateSession: vi.fn(),
    useDeleteSession: vi.fn(),
  };
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

const renderPage = () => {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SessionsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe('SessionsPage', () => {
  it('opens and closes delete modal correctly on successful delete', async () => {
    // Setup mocks
    const mockMutateAsync = vi.fn().mockResolvedValue({});
    (Queries.useSessions as Mock).mockReturnValue({
      isLoading: false,
      data: [
        {
          id: '123',
          title: 'Test Session',
          created_at: new Date().toISOString(),
        },
      ],
    });
    (Queries.useCreateSession as Mock).mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn(),
    });
    (Queries.useDeleteSession as Mock).mockReturnValue({
      isPending: false,
      mutateAsync: mockMutateAsync,
    });

    renderPage();

    // 1. Click delete icon
    const deleteBtn = screen.getByTestId('DeleteOutlineIcon').closest('button');
    expect(deleteBtn).toBeInTheDocument();
    fireEvent.click(deleteBtn!);

    // 2. Verify modal opens
    expect(await screen.findByText('Delete Session?')).toBeInTheDocument();

    // 3. Click Confirm Delete
    const confirmBtn = screen.getByText('Delete', { selector: 'button' });
    fireEvent.click(confirmBtn);

    // 4. Verify mutateAsync was called
    expect(mockMutateAsync).toHaveBeenCalledWith('123');

    // 5. Verify modal closes
    await waitFor(() => {
      expect(screen.queryByText('Delete Session?')).not.toBeInTheDocument();
    });
  });

  it('closes modal even if delete fails (graceful degradation)', async () => {
    // Setup mocks for failure
    const mockMutateAsync = vi.fn().mockRejectedValue(new Error('Delete invalid'));
    (Queries.useSessions as Mock).mockReturnValue({
      isLoading: false,
      data: [
        {
          id: '123',
          title: 'Test Session',
          created_at: new Date().toISOString(),
        },
      ],
    });
    (Queries.useCreateSession as Mock).mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn(),
    });
    (Queries.useDeleteSession as Mock).mockReturnValue({
      isPending: false,
      mutateAsync: mockMutateAsync,
    });

    renderPage();

    // 1. Click delete icon
    const deleteBtn = screen.getByTestId('DeleteOutlineIcon').closest('button');
    fireEvent.click(deleteBtn!);

    // 2. Verified modal opens
    expect(await screen.findByText('Delete Session?')).toBeInTheDocument();

    // 3. Click Confirm Delete
    const confirmBtn = screen.getByText('Delete', { selector: 'button' });
    fireEvent.click(confirmBtn);

    // 4. Verify interaction
    expect(mockMutateAsync).toHaveBeenCalled();

    // 5. Verify modal closes (due to finally block)
    await waitFor(() => {
      expect(screen.queryByText('Delete Session?')).not.toBeInTheDocument();
    });
  });
});

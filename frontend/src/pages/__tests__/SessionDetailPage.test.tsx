import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, type Mock } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionDetailPage } from "../SessionDetailPage";
import * as Queries from "../../api/queries";

// Mock the API hooks
vi.mock("../../api/queries", async () => {
  const actual = await vi.importActual("../../api/queries");
  return {
    ...actual,
    useSession: vi.fn(),
    useSteps: vi.fn(),
    useCasts: vi.fn(),
    usePendingRequests: vi.fn(),
    useAllowPending: vi.fn(),
    useDenyPending: vi.fn(),
    useSessions: vi.fn(), // for sidebar
  };
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

const renderPage = (sessionId = "123") => {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/sessions/${sessionId}`]}>
        <Routes>
          <Route path="/sessions/:sessionId" element={<SessionDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe("SessionDetailPage", () => {
  it("renders loading state initially", () => {
    (Queries.useSession as Mock).mockReturnValue({ isLoading: true });
    (Queries.useSteps as Mock).mockReturnValue({ isLoading: true });
    (Queries.useSessions as Mock).mockReturnValue({ data: [] });

    renderPage();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("renders session title and steps when loaded", async () => {
    (Queries.useSession as Mock).mockReturnValue({
      isLoading: false,
      data: {
        id: "123",
        title: "My Session",
        created_at: new Date().toISOString(),
      },
    });
    (Queries.useSteps as Mock).mockReturnValue({
      isLoading: false,
      data: [
        {
          id: "step-1",
          name: "step 1",
          kind: "tool_call",
          status: "ok",
          created_at: new Date().toISOString(),
        },
      ],
    });
    (Queries.useCasts as Mock).mockReturnValue({ data: [] });
    (Queries.usePendingRequests as Mock).mockReturnValue({ data: [] });
    (Queries.useAllowPending as Mock).mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    });
    (Queries.useDenyPending as Mock).mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    });
    (Queries.useSessions as Mock).mockReturnValue({ data: [] });

    renderPage();

    expect(await screen.findByText("My Session")).toBeInTheDocument();
  });

  it("renders 404 state when session is missing", async () => {
    // Mock the ApiError we added
    const { ApiError } = await import("../../api/client");
    (Queries.useSession as Mock).mockReturnValue({
      isLoading: false,
      error: new ApiError(404, "Not found"),
    });
    (Queries.useSteps as Mock).mockReturnValue({ isLoading: false, data: [] });

    renderPage();

    expect(await screen.findByText("Session Not Found")).toBeInTheDocument();
  });
});

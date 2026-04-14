import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Sidebar from "@/components/Sidebar";
import Landing from "@/pages/Landing";
import NotFound from "@/pages/NotFound";
import Onboarding from "@/pages/Onboarding";
import { sentinelApi } from "@/lib/api";

function createTestClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

describe("frontend product shell", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the landing page with real product messaging", async () => {
    vi.spyOn(sentinelApi, "getReadiness").mockResolvedValue({
      status: "ready",
      model_loaded: true,
      redis_connected: true,
      db_connected: true,
      details: {},
    });
    vi.spyOn(sentinelApi, "getHealth").mockResolvedValue({
      status: "ok",
      version: "v1.0.0",
      timestamp: "2026-04-14T10:00:00Z",
    });

    render(
      <QueryClientProvider client={createTestClient()}>
        <MemoryRouter>
          <Landing />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText("The command layer for traders you cannot afford to lose."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Real answers for the product we are actually shipping."),
    ).toBeInTheDocument();
    expect(screen.getByText("Platform facts")).toBeInTheDocument();
  });

  it("keeps operator-only admin navigation out of the default sidebar", () => {
    render(
      <MemoryRouter initialEntries={["/workspace"]}>
        <Sidebar />
      </MemoryRouter>,
    );

    expect(screen.getByText("Command")).toBeInTheDocument();
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
  });

  it("shows the onboarding history selector and zero-trust messaging", () => {
    render(
      <MemoryRouter>
        <Onboarding identity={null} onConnected={vi.fn()} />
      </MemoryRouter>,
    );

    expect(screen.getByText("ZERO-TRUST STORAGE")).toBeInTheDocument();
    expect(screen.getByLabelText("MINIMUM HISTORY")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "100 trades" })).toBeInTheDocument();
  });

  it("renders a guided 404 surface for unknown routes", () => {
    render(
      <MemoryRouter initialEntries={["/ghost-route"]}>
        <NotFound />
      </MemoryRouter>,
    );

    expect(screen.getByText("Route not found")).toBeInTheDocument();
    expect(screen.getByText("/ghost-route")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Landing page/i })).toBeInTheDocument();
  });
});

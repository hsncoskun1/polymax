import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import App from "../App";

function renderWithRouter(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>
  );
}

describe("App routing", () => {
  it("renders POLYMAX header", () => {
    renderWithRouter("/user");
    expect(screen.getByText("POLYMAX")).toBeDefined();
  });

  it("renders User Panel on /user", () => {
    renderWithRouter("/user");
    expect(screen.getByText("User Panel")).toBeDefined();
  });

  it("renders Admin Panel on /admin", () => {
    renderWithRouter("/admin");
    expect(screen.getByText("Admin Panel")).toBeDefined();
  });

  it("redirects unknown routes to /user", () => {
    renderWithRouter("/unknown");
    expect(screen.getByText("User Panel")).toBeDefined();
  });

  it("shows nav tabs for User and Admin", () => {
    renderWithRouter("/user");
    expect(screen.getByText("User")).toBeDefined();
    expect(screen.getByText("Admin")).toBeDefined();
  });
});

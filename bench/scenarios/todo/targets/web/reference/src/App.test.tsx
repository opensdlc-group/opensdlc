import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { App } from "./App";

afterEach(cleanup);

describe("App", () => {
  it("shows the heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Todos" })).toBeTruthy();
  });

  it("adds a trimmed todo and rejects an empty one", () => {
    render(<App />);
    fireEvent.change(screen.getByTestId("new-todo-title"), { target: { value: "  Milk  " } });
    fireEvent.click(screen.getByTestId("add-todo"));
    expect(screen.getByTestId("todo-title").textContent).toBe("Milk");
    fireEvent.click(screen.getByTestId("add-todo"));
    expect(screen.getByTestId("error")).toBeTruthy();
  });
});

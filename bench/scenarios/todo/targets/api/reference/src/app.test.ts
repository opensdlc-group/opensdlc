import { describe, expect, it } from "vitest";
import { createApp } from "./app";

describe("todos", () => {
  it("lists dated todos first", async () => {
    const app = createApp();
    await app.request("/todos", { method: "POST", body: JSON.stringify({ title: "later" }) });
    await app.request("/todos", { method: "POST", body: JSON.stringify({ title: "soon", due: "2026-01-02" }) });
    const todos = await (await app.request("/todos")).json();
    expect(todos.map((t: { title: string }) => t.title)).toEqual(["soon", "later"]);
  });

  it("rejects an impossible date", async () => {
    const response = await createApp().request("/todos", { method: "POST", body: JSON.stringify({ title: "x", due: "2026-02-30" }) });
    expect(response.status).toBe(400);
  });
});

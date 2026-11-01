import { describe, expect, it } from "vitest";
import { app } from "./app";

describe("health", () => {
  it("reports ok", async () => {
    const response = await app.request("/health");
    expect(response.status).toBe(200);
  });
});

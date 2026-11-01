import { Hono } from "hono";
import { InvalidTodo, TodoStore, UnknownTodo } from "./todos";

export function createApp(store = new TodoStore()): Hono {
  const app = new Hono();

  app.onError((error, c) => {
    if (error instanceof InvalidTodo) return c.json({ error: error.message }, 400);
    if (error instanceof UnknownTodo) return c.json({ error: error.message }, 404);
    throw error;
  });

  app.get("/health", (c) => c.json({ ok: true }));
  app.get("/todos", (c) => {
    const shown = c.req.query("remaining") === "true" ? store.list().filter((t) => !t.done) : store.list();
    return c.json(shown.map((todo, index) => ({ ...todo, position: index + 1 })));
  });
  app.post("/todos", async (c) => {
    const body = await c.req.json().catch(() => ({}));
    return c.json(store.add(body.title, body.due), 201);
  });
  app.post("/todos/clear-completed", (c) => c.json({ removed: store.clearCompleted() }));
  app.post("/todos/:id/complete", (c) => c.json(store.complete(c.req.param("id"))));
  app.delete("/todos/:id", (c) => {
    store.delete(c.req.param("id"));
    return c.body(null, 204);
  });

  return app;
}

export const app = createApp();

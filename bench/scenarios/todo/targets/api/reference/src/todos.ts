export type Todo = { id: string; title: string; done: boolean; due: string | null };

export class InvalidTodo extends Error {}
export class UnknownTodo extends Error {}

const MAX_TITLE = 200;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function cleanTitle(raw: unknown): string {
  const title = typeof raw === "string" ? raw.trim() : "";
  const length = [...title].length;
  if (length < 1 || length > MAX_TITLE) throw new InvalidTodo(`a title needs 1 to ${MAX_TITLE} characters`);
  return title;
}

function cleanDue(raw: unknown): string | null {
  if (raw === undefined || raw === null) return null;
  const valid = typeof raw === "string" && ISO_DATE.test(raw) && new Date(`${raw}T00:00:00Z`).toISOString().startsWith(raw);
  if (!valid) throw new InvalidTodo(`'${String(raw)}' is not a date in YYYY-MM-DD form`);
  return raw as string;
}

export class TodoStore {
  private todos: Todo[] = [];
  private nextId = 1;

  add(title: unknown, due: unknown): Todo {
    const todo = { id: "", title: cleanTitle(title), done: false, due: cleanDue(due) };
    todo.id = String(this.nextId++);
    this.todos.push(todo);
    return todo;
  }

  list(): Todo[] {
    return [...this.todos].sort((a, b) => Number(a.due === null) - Number(b.due === null) || (a.due ?? "").localeCompare(b.due ?? ""));
  }

  find(id: string): Todo {
    const todo = this.todos.find((t) => t.id === id);
    if (!todo) throw new UnknownTodo(`no todo with id ${id}`);
    return todo;
  }

  complete(id: string): Todo {
    const todo = this.find(id);
    todo.done = true;
    return todo;
  }

  delete(id: string): void {
    const todo = this.find(id);
    this.todos = this.todos.filter((t) => t !== todo);
  }

  clearCompleted(): number {
    const before = this.todos.length;
    this.todos = this.todos.filter((t) => !t.done);
    return before - this.todos.length;
  }
}

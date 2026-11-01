import { type FormEvent, useRef, useState } from "react";
import { cleanTitle, inListOrder, type Todo } from "./todos";

export function App() {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cleared, setCleared] = useState<number | null>(null);
  const [remainingOnly, setRemainingOnly] = useState(false);
  const nextId = useRef(1);

  function add(event: FormEvent) {
    event.preventDefault();
    const clean = cleanTitle(title);
    if (clean === null) {
      setError("A title needs 1 to 200 characters.");
      return;
    }
    const todo = { id: nextId.current++, title: clean, done: false, due: due || null };
    setTodos((current) => [...current, todo]);
    setTitle("");
    setDue("");
    setError(null);
  }

  function complete(id: number) {
    setTodos((current) => current.map((t) => (t.id === id ? { ...t, done: true } : t)));
    setError(null);
  }

  function remove(id: number) {
    setTodos((current) => current.filter((t) => t.id !== id));
    setError(null);
  }

  function clearCompleted() {
    setCleared(todos.filter((t) => t.done).length);
    setTodos(todos.filter((t) => !t.done));
    setError(null);
  }

  return (
    <main>
      <h1>Todos</h1>
      <form onSubmit={add}>
        <input data-testid="new-todo-title" aria-label="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input data-testid="new-todo-due" aria-label="Due date" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        <button data-testid="add-todo" type="submit">Add</button>
      </form>
      {error && <p data-testid="error" role="alert">{error}</p>}
      <ul>
        {inListOrder(remainingOnly ? todos.filter((t) => !t.done) : todos).map((todo, index) => (
          <li key={todo.id} data-testid="todo-item" data-id={todo.id} data-done={String(todo.done)}>
            <span data-testid="todo-position">{index + 1}</span>
            <span data-testid="todo-title">{todo.title}</span>
            {todo.due && <span data-testid="todo-due">{todo.due}</span>}
            <button data-testid="complete-todo" type="button" onClick={() => complete(todo.id)}>Done</button>
            <button data-testid="delete-todo" type="button" onClick={() => remove(todo.id)}>Delete</button>
          </li>
        ))}
      </ul>
      <label>
        <input data-testid="remaining-only" type="checkbox" checked={remainingOnly} onChange={(e) => setRemainingOnly(e.target.checked)} />
        Remaining only
      </label>
      <button data-testid="clear-completed" type="button" onClick={clearCompleted}>Clear completed</button>
      {cleared !== null && <p data-testid="cleared-count">{cleared} removed</p>}
    </main>
  );
}

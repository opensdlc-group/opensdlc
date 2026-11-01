export type Todo = { id: number; title: string; done: boolean; due: string | null };

const MAX_TITLE = 200;

export function cleanTitle(raw: string): string | null {
  const title = raw.trim();
  const length = [...title].length;
  return length >= 1 && length <= MAX_TITLE ? title : null;
}

export function inListOrder(todos: Todo[]): Todo[] {
  return [...todos].sort((a, b) => Number(a.due === null) - Number(b.due === null) || (a.due ?? "").localeCompare(b.due ?? ""));
}

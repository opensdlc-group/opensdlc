# Glossary

## Done
A todo someone has ticked off. It stays in the list until it is cleared or deleted.
Not to be confused with: deleted, which removes the todo from the list.
Example: ticking off "Buy milk" marks it done; it is still listed.

## Id
The identifier the product gives a todo when it is added, used to tick it off or delete it. It never changes and is never given to another todo ([ADR 0001](docs/adr/0001-todo-ids-are-permanent.md)).
Not to be confused with: a todo's place in the list, which changes as todos come and go.
Example: the third todo ever added keeps its id after the first two are deleted.

## Title
What a todo says, as the person typed it, with spaces at either end dropped.
Example: "  Buy milk " is saved as "Buy milk".

## Todo
One thing someone means to do: a title, an id, and whether it is done. Tickets add to it.

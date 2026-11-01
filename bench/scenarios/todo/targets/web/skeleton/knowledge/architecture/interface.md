---
kind: architecture
owner: product-owner
review-by: 2027-12-31
always: true
---
# Web app

The page is the product. Automated end-to-end tests drive it through `data-testid` attributes, so those are a contract.

- `npm run build` builds a static single page. Todos live in memory; reloading starts empty.
- `new-todo-title` is the title input and `add-todo` the button that adds; pressing Enter in the input adds too.
- Each todo is a `todo-item` element with `data-id` (its id) and `data-done` (`"true"` or `"false"`), containing a `todo-title` with the title.
- Invalid input shows an `error` element with a message and adds nothing. The message goes away after the next successful action.

---
kind: architecture
owner: product-owner
review-by: 2027-12-31
always: true
---
# HTTP API

The API is the product. Other services call it, so this contract holds for every endpoint.

- `npm start` serves it on the port in the `PORT` environment variable. `GET /health` answers 200.
- Todos live in memory; a restart starts empty.
- Request and response bodies are JSON. A todo is an object with `id` (a string), `title` and `done`. Tickets add fields.
- Invalid input answers 400 and an unknown id answers 404, each with `{"error": "<message>"}`. Neither changes anything.

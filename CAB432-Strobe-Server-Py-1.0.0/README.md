# Strobe Server (Python)

Strobe is a platform for sharing photos with family and friends. It was developed for CAB432 Cloud Computing at the Queensland University of Technology.

With thanks to Jackson Riding for the development of Strobe Server.

This is the Python implementation of Strobe Server. There is also a JavaScript implementation.

Copyright (c) 2026 Queensland University of Technology

This software is not open source and remains property of the Queensland University of Technology. Unauthorised distribution is not permitted.

## Development

```bash
pip install -r requirements.txt
python -m src.scripts.seed
uvicorn src.main:app --reload --port 3000
```

## Server URL Configuration (Important)

The Python server controls where this API listens and what public URLs it returns for generated upload links.

Copy `.env.example` to `.env` and edit:

```text
PORT=3000
HOST=0.0.0.0
PUBLIC_BASE_URL=http://localhost:3000
```

The server automatically loads `.env` from this folder. Values already set in your shell take priority over `.env`.

- `PORT`: HTTP port the API listens on.
- `HOST`: Bind host (`0.0.0.0` for all interfaces, `127.0.0.1` for local-only).
- `PUBLIC_BASE_URL`: Optional absolute base URL for upload URLs returned by this API.

If `PUBLIC_BASE_URL` is empty, upload URLs are returned as relative paths.

This does not change the React client's Connected API. Use `client/.env` or the login/signup screen API control for that.

## Notes

- Database state is stored in `db.json` at the root of this folder.
- `python -m src.scripts.seed` resets and repopulates the Python database with the same sample collections as the Node seed script.

## Useful notes

- Seed uses `password123` for generated users.
- The first seeded user is a moderator.
- Protected routes require a bearer token in the Authorization header.
- Import insomnia/strobe-openapi.yaml into Insomnia for ready-to-use requests.

## Insomnia

Import this file:

```text
insomnia/strobe-openapi.yaml
```

Set base URL to:

```text
http://localhost:3000
```

For protected routes, send:

```text
Authorization: Bearer <token>
```

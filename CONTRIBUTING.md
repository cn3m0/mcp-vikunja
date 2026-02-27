# Contributing

## Development Flow

1. Create `.env` from `.env.example` (if missing).
2. Start services:

```bash
make up
```

3. Bootstrap admin and API token:

```bash
make bootstrap
```

4. Run checks before committing:

```bash
make full-check
```

## Commit Guidelines

- Keep commits small and focused.
- Do not commit secrets (`.env` is ignored).
- Update docs when behavior or commands change.

## Pull Request Checklist

- `make full-check` passes locally.
- `docker compose config` is valid.
- README changes are included when needed.


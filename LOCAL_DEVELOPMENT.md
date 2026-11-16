# Local Development

This project can run against a local-only D1 database for Pages development.

## Local D1 mode

Cloudflare's current Pages + D1 flow supports local D1 development through `wrangler pages dev --local` and `wrangler d1 execute --local`. The local database is separate from the remote Cloudflare D1 database.

Required setup:

1. Copy `.dev.vars.example` to `.dev.vars`.
2. Set `DASHBOARD_DATA_MODE=snapshot` in `.dev.vars`.
3. Initialize the local schema:

```bash
npm run d1:local:init
```

4. Seed demo data:

```bash
npm run d1:local:seed
```

5. Start the app:

```bash
npm run dev:local
```

With `DASHBOARD_DATA_MODE=snapshot`, `/api/dashboard` uses the latest snapshot already stored in local D1 as the current dashboard payload. This avoids depending on the remote D1 database and makes compare/history/delete flows testable with seeded data.

## Sync real remote data into local D1

If you want local development to use the current remote Cloudflare D1 contents instead of demo seed data:

```bash
CLOUDFLARE_API_TOKEN=your_token_here \
npm run d1:local:sync
```

This does three things:

1. Exports the remote D1 database to a temporary SQL file.
2. Resets the local D1 database.
3. Imports the remote SQL into local D1.

The token must have D1 access to the target database.

After sync, keep `DASHBOARD_DATA_MODE=snapshot` and start local dev:

```bash
npm run dev:local
```

## Reset local data

```bash
npm run d1:local:reset
npm run d1:local:init
npm run d1:local:seed
```

## Notes

- Local D1 data is persisted under Wrangler's local state and is separate from production.
- `refresh` still uses live Polymarket and pUSD APIs. For pure local UI testing, avoid clicking refresh and stay in `snapshot` mode.
- The local seed includes two snapshots, positions, and pUSD balances for the default wallet address.

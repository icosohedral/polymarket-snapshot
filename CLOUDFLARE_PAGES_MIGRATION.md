# Cloudflare Pages Migration

## Current status

The repository now has the basic Cloudflare Pages shape:

- `public/index.html`: static dashboard entrypoint
- `functions/api/`: Pages Functions API handlers will go here
- `src/lib/`: shared TypeScript/JavaScript modules will go here
- `wrangler.toml`: local Pages config

## Local development target

After the Functions layer exists, local development will be:

```bash
npx wrangler pages dev public
```

## Migration order

1. Move the static page to `public/index.html`
2. Recreate `/api/dashboard`
3. Recreate `/api/compare`
4. Recreate `/api/refresh`
5. Recreate `/api/delete-snapshot`
6. Replace Python D1 REST usage with Cloudflare D1 binding
7. Move sensitive config from `config.json` to Cloudflare environment variables

## Important note

The current Python files are still the source of truth for business logic.
At this stage, Pages deployment is not complete yet because the API layer has not been migrated.

## Current migrated route

The first Pages route has been implemented:

- `functions/api/dashboard.ts`
- `functions/api/compare.ts`
- `functions/api/refresh.ts`
- `functions/api/delete-snapshot.ts`

It currently depends on:

- D1 binding named `DB`
- environment variable `POLYMARKET_USER_ADDRESS` or `wallet` query param
- environment variable `ETHERSCAN_API_KEY`
- optional environment variables `PUSD_CONTRACT_ADDRESS`, `CHAIN_ID`, `SNAPSHOT_RETENTION`

## Required Cloudflare bindings

Add a D1 binding in Cloudflare Pages:

- Binding name: `DB`
- Database: your existing D1 database

## Required environment variables

Set these in Pages project settings:

- `POLYMARKET_USER_ADDRESS`
- `ETHERSCAN_API_KEY`

Optional:

- `PUSD_CONTRACT_ADDRESS`
- `CHAIN_ID`
- `SNAPSHOT_RETENTION`

## Current configuration you need in Cloudflare Pages

In `Settings -> Functions -> D1 bindings`:

- `DB` -> your D1 database

In `Settings -> Environment variables`:

- `POLYMARKET_USER_ADDRESS`
- `ETHERSCAN_API_KEY`

Optional:

- `PUSD_CONTRACT_ADDRESS`
- `CHAIN_ID`
- `SNAPSHOT_RETENTION`

At this stage you do not need Cloudflare API token / account ID / database ID in env for Pages runtime,
because the migrated Pages routes are using the D1 binding directly instead of the D1 REST API.

## Migration status

Migrated API routes:

- `/api/dashboard`
- `/api/compare`
- `/api/refresh`
- `/api/delete-snapshot`

Still recommended before production cutover:

- run local `wrangler pages dev` validation
- move frontend source of truth from root `dashboard.html` to `public/index.html`
- remove old Python server path after Pages deployment is verified

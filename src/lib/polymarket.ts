import { boolToInt, safeNumber } from "./runtime";

const POLYMARKET_POSITIONS_URL = "https://data-api.polymarket.com/v2/positions";
// Upstream calls must not hang a whole refresh.
const REQUEST_TIMEOUT_MS = 10_000;
const USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36";

// Polymarket rate-limits Cloudflare's shared egress with 429s; back off briefly
// before giving up, honouring a short Retry-After when one is sent.
const RETRY_DELAYS_MS = [800, 2_000];

async function fetchWithRetry(url: string): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    const response = await fetch(url, {
      headers: { "Accept": "application/json", "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    if (response.status !== 429 || attempt >= RETRY_DELAYS_MS.length) {
      return response;
    }
    const retryAfterMs = Number(response.headers.get("Retry-After")) * 1000;
    const delay =
      retryAfterMs > 0 && retryAfterMs <= 3_000 ? retryAfterMs : RETRY_DELAYS_MS[attempt];
    await new Promise((resolve) => setTimeout(resolve, delay));
  }
}

export type RawPosition = Record<string, unknown>;
export type DashboardPosition = Record<string, unknown>;

export async function fetchAllPositions(
  walletAddress: string,
  pageLimit = 100,
): Promise<RawPosition[]> {
  const allRows: RawPosition[] = [];
  let cursor: string | null = null;

  // Data API v2: cursor-based pagination, response is { data, pagination }.
  for (let page = 0; page < 1000; page++) {
    const url = new URL(POLYMARKET_POSITIONS_URL);
    url.searchParams.set("user", walletAddress);
    url.searchParams.set("limit", String(pageLimit));
    url.searchParams.set("sortBy", "CURRENT_VALUE");
    url.searchParams.set("sortDirection", "DESC");
    url.searchParams.set("sizeThreshold", "0");
    if (cursor) {
      url.searchParams.set("cursor", cursor);
    }

    const response = await fetchWithRetry(url.toString());
    if (!response.ok) {
      const detail = await response.text().catch(() => "");
      throw new Error(
        `Polymarket request failed: ${response.status}${detail ? ` ${detail.slice(0, 200)}` : ""}`,
      );
    }

    const body = (await response.json()) as {
      data?: unknown;
      pagination?: { has_more?: boolean; next_cursor?: string | null };
    };
    if (!body || !Array.isArray(body.data)) {
      throw new Error("Unexpected Polymarket response format");
    }

    allRows.push(...(body.data as RawPosition[]));

    const next = body.pagination?.next_cursor;
    if (!body.pagination?.has_more || !next) {
      break;
    }
    cursor = next;
  }

  return allRows;
}

// Realized PnL of closed positions for the given markets, keyed by `${condition_id}::${outcome}`.
export async function fetchClosedRealizedPnl(
  walletAddress: string,
  conditionIds: string[],
): Promise<Map<string, number>> {
  const result = new Map<string, number>();
  // One malformed id makes the API reject the whole batch, so only send real condition ids.
  const unique = [
    ...new Set(conditionIds.filter((id) => /^0x[0-9a-fA-F]{64}$/.test(String(id || "")))),
  ];

  for (let index = 0; index < unique.length; index += 40) {
    const chunk = unique.slice(index, index + 40);
    const url = new URL(POLYMARKET_POSITIONS_URL);
    url.searchParams.set("user", walletAddress);
    url.searchParams.set("status", "CLOSED");
    url.searchParams.set("limit", "500");
    url.searchParams.set("condition", chunk.join(","));

    const response = await fetchWithRetry(url.toString());
    if (!response.ok) {
      throw new Error(`Polymarket closed positions request failed: ${response.status}`);
    }
    const body = (await response.json()) as { data?: unknown };
    if (!Array.isArray(body?.data)) {
      continue;
    }
    for (const row of body.data as RawPosition[]) {
      const key = `${row.condition_id}::${row.outcome}`;
      result.set(key, safeNumber(result.get(key)) + safeNumber(row.realized_pnl));
    }
  }

  return result;
}

// Map Data API v2 (snake_case) rows to the legacy v1 shape used by D1 and the dashboard.
export function simplifyPosition(row: RawPosition): Record<string, unknown> {
  return {
    title: row.title,
    outcome: row.outcome,
    size: row.current_size,
    avgPrice: row.avg_price,
    curPrice: row.current_price,
    initialValue: row.entry_cost_usdc,
    currentValue: row.current_value,
    cashPnl: row.unrealized_pnl,
    percentPnl: row.percent_pnl,
    realizedPnl: row.realized_pnl,
    percentRealizedPnl: row.percent_realized_pnl,
    slug: row.slug,
    eventSlug: row.event_slug,
    conditionId: row.condition_id,
    asset: row.token_id,
    oppositeAsset: row.opposite_token_id,
    endDate: row.end_date,
    redeemable: row.redeemable,
    mergeable: row.mergeable,
    negativeRisk: row.negative_risk,
    icon: row.icon,
  };
}

export function normalizePositionForDashboard(
  position: Record<string, unknown>,
  walletAddress: string,
  snapshotId: number | null = null,
): DashboardPosition {
  return {
    id: null,
    snapshot_id: snapshotId,
    wallet_address: walletAddress,
    condition_id: position.conditionId,
    asset: position.asset,
    opposite_asset: position.oppositeAsset,
    title: position.title,
    event_slug: position.eventSlug,
    slug: position.slug,
    outcome: position.outcome,
    size: position.size,
    avg_price: position.avgPrice,
    cur_price: position.curPrice,
    initial_value: position.initialValue,
    current_value: position.currentValue,
    cash_pnl: position.cashPnl,
    percent_pnl: position.percentPnl,
    realized_pnl: position.realizedPnl,
    percent_realized_pnl: position.percentRealizedPnl,
    end_date: position.endDate,
    redeemable: boolToInt(position.redeemable),
    mergeable: boolToInt(position.mergeable),
    negative_risk: boolToInt(position.negativeRisk),
    icon: typeof position.icon === "string" ? position.icon : null,
    created_at: null,
  };
}

export function summarizePositions(positions: Array<Record<string, unknown>>) {
  const positionsInitialValue = round2(
    positions.reduce((sum, row) => sum + safeNumber(row.initialValue), 0),
  );
  const positionsCurrentValue = round2(
    positions.reduce((sum, row) => sum + safeNumber(row.currentValue), 0),
  );
  const positionsCashPnl = round2(
    positions.reduce((sum, row) => sum + safeNumber(row.cashPnl), 0),
  );
  const positionsRealizedPnl = round2(
    positions.reduce((sum, row) => sum + safeNumber(row.realizedPnl), 0),
  );

  return {
    positionsCount: positions.length,
    positionsInitialValue,
    positionsCurrentValue,
    positionsCashPnl,
    positionsRealizedPnl,
  };
}

export function isActivePosition(position: Record<string, unknown>): boolean {
  if (Number(position.redeemable || 0) === 1) {
    return false;
  }
  // end_date is only the scheduled date; markets often stay open past it until
  // they resolve, so it must not decide whether a position is still held.
  return safeNumber(position.current_value) >= 1;
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}


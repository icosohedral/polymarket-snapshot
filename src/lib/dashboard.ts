import type { AppEnv } from "./runtime";
import {
  DEFAULT_USER,
  resolveRuntimeSettings,
  safeNumber,
  utcNowIso,
} from "./runtime";
import {
  fetchAllPositions,
  DashboardPosition,
  RawPosition,
  isActivePosition,
  normalizePositionForDashboard,
  simplifyPosition,
  summarizePositions,
} from "./polymarket";
import { getPusdBalance } from "./wallet";
import {
  getLatestSnapshot,
  getSnapshotPositions,
  getSnapshotTokenBalances,
} from "./d1";

export type PrefetchedLiveData = {
  rows: RawPosition[];
  usdcResult: Awaited<ReturnType<typeof getPusdBalance>>;
};

export async function fetchLiveData(
  settings: ReturnType<typeof resolveRuntimeSettings>,
): Promise<PrefetchedLiveData> {
  // Independent upstreams: fetch them in parallel.
  const [rows, usdcResult] = await Promise.all([
    fetchAllPositions(settings.walletAddress),
    getPusdBalance({
      apiKey: settings.etherscanApiKey,
      userAddress: settings.walletAddress,
      pusdContractAddress: settings.pusdContractAddress,
      chainId: settings.chainId,
    }),
  ]);
  return { rows, usdcResult };
}

export async function buildLiveDashboardPayload(
  env: AppEnv,
  walletAddress?: string | null,
  prefetched?: PrefetchedLiveData,
) {
  const settings = resolveRuntimeSettings(env, walletAddress);
  if (settings.dashboardDataMode === "snapshot") {
    return buildSnapshotDashboardPayload(env.DB, settings.walletAddress);
  }

  let live: PrefetchedLiveData;
  try {
    live = prefetched ?? (await fetchLiveData(settings));
  } catch (error) {
    // Live data unavailable (e.g. Polymarket 429): serve the latest stored snapshot
    // instead of failing the whole page. Explicit refreshes (prefetched) still fail loudly.
    const fallback = await buildSnapshotDashboardPayload(env.DB, settings.walletAddress);
    if (!fallback.snapshot) {
      throw error;
    }
    return {
      ...fallback,
      live: {
        source: "snapshot_fallback",
        error: error instanceof Error ? error.message : String(error),
      },
    };
  }
  const { rows, usdcResult } = live;
  const positions = rows.map(simplifyPosition);
  const dashboardPositions = positions
    .map((position) => normalizePositionForDashboard(position, settings.walletAddress))
    .filter((position) => isActivePosition(position));

  const summary = summarizePositions(positions);
  const usdcBalance = usdcResult.result ? safeNumber(usdcResult.data) : 0;
  const totalAssets = Math.round((usdcBalance + summary.positionsCurrentValue) * 100) / 100;
  const history = await getSnapshotHistory(env.DB, settings.walletAddress, 20);

  return {
    walletAddress: settings.walletAddress,
    snapshot: {
      id: null,
      wallet_address: settings.walletAddress,
      snapshot_at: utcNowIso(),
      usdc_balance: usdcBalance,
      positions_current_value: summary.positionsCurrentValue,
      positions_initial_value: summary.positionsInitialValue,
      positions_cash_pnl: summary.positionsCashPnl,
      positions_realized_pnl: summary.positionsRealizedPnl,
      total_assets: totalAssets,
      positions_count: summary.positionsCount,
      source: "live_dashboard",
    },
    positions: dashboardPositions,
    tokenBalances: [],
    history,
    live: {
      usdcResult,
      source: "live_dashboard",
    },
  };
}

async function buildSnapshotDashboardPayload(
  db: D1Database,
  walletAddress: string,
) {
  const snapshot = await getLatestSnapshot(db, walletAddress);
  const history = await getSnapshotHistory(db, walletAddress, 20);

  if (!snapshot) {
    return {
      walletAddress: walletAddress || DEFAULT_USER,
      snapshot: null,
      positions: [],
      tokenBalances: [],
      history,
      live: {
        source: "snapshot_dashboard",
      },
    };
  }

  const snapshotId = Number(snapshot.id || 0);
  const positions = snapshotId
    ? ((await getSnapshotPositions(db, snapshotId)).filter((row) =>
        isActivePosition(row),
      ) as DashboardPosition[])
    : [];
  const tokenBalances = snapshotId ? await getSnapshotTokenBalances(db, snapshotId) : [];

  return {
    walletAddress,
    snapshot,
    positions,
    tokenBalances,
    history,
    live: {
      source: "snapshot_dashboard",
    },
  };
}

async function getSnapshotHistory(
  db: D1Database,
  walletAddress: string,
  limit = 20,
): Promise<Record<string, unknown>[]> {
  const result = await db
    .prepare(
      `
      SELECT
        id,
        snapshot_at,
        usdc_balance,
        positions_current_value,
        positions_cash_pnl,
        total_assets,
        positions_count
      FROM wallet_snapshots
      WHERE wallet_address = ?
      ORDER BY snapshot_at DESC, id DESC
      LIMIT ?
      `,
    )
    .bind(walletAddress, limit)
    .all<Record<string, unknown>>();

  return Array.isArray(result.results) ? result.results : [];
}

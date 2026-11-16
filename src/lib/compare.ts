import { buildLiveDashboardPayload } from "./dashboard";
import { getSnapshot, getSnapshotPositions } from "./d1";
import type { AppEnv } from "./runtime";
import { safeNumber } from "./runtime";
import { fetchClosedRealizedPnl, isActivePosition } from "./polymarket";

export async function buildComparePayload(
  env: AppEnv,
  compareSnapshotId: number,
  walletAddress?: string | null,
) {
  const current = await buildLiveDashboardPayload(env, walletAddress);
  const resolvedWalletAddress = String(current.walletAddress || walletAddress || "");

  if (!current.snapshot) {
    return {
      walletAddress: resolvedWalletAddress,
      snapshot: null,
      compareSnapshot: null,
      positions: [],
    };
  }

  const compareSnapshot = await getSnapshot(env.DB, compareSnapshotId);
  if (!compareSnapshot) {
    throw new Error(`Snapshot not found: ${compareSnapshotId}`);
  }
  if (compareSnapshot.wallet_address !== resolvedWalletAddress) {
    throw new Error("Snapshot does not belong to the current wallet");
  }

  const latestPositions = (current.positions || []).filter((row) =>
    isActivePosition(row as Record<string, unknown>),
  ) as Record<string, unknown>[];
  const comparePositions = filterHeldAtSnapshot(await getSnapshotPositions(env.DB, compareSnapshotId));
  const compareMap = new Map<string, Record<string, unknown>>();
  for (const row of comparePositions) {
    compareMap.set(`${row.condition_id}::${row.outcome}`, row);
  }

  const matchedKeys = new Set<string>();
  const mergedPositions: Record<string, unknown>[] = latestPositions.map((row) => {
    const key = `${row.condition_id}::${row.outcome}`;
    const previous = compareMap.get(key);
    if (previous) {
      matchedKeys.add(key);
    }
    const previousSize = safeNumber(previous?.size);
    const currentSize = safeNumber(row.size);
    const currentValue = safeNumber(row.current_value);
    const diffSize = round(currentSize - previousSize, 4);
    const diffCurrentValue = round(currentValue - safeNumber(previous?.current_value), 2);

    return {
      ...row,
      diff_size: diffSize,
      diff_current_value: diffCurrentValue,
      previous_size: previous ? previousSize : null,
      change_status: classifyChange(Boolean(previous), previousSize, diffSize, diffCurrentValue),
    };
  });

  // "Closed" only covers markets still held in the most recent stored snapshot,
  // whichever snapshot is being compared against.
  const closedSince = await getPreviousSnapshot(
    env.DB,
    resolvedWalletAddress,
    Number(current.snapshot.id || 0) || null,
  );
  const closedSourcePositions = !closedSince
    ? []
    : Number(closedSince.id) === Number(compareSnapshot.id)
      ? comparePositions
      : filterHeldAtSnapshot(await getSnapshotPositions(env.DB, Number(closedSince.id)));
  const currentKeys = new Set(latestPositions.map((row) => `${row.condition_id}::${row.outcome}`));
  const closedRows = closedSourcePositions.filter(
    (row) => !currentKeys.has(`${row.condition_id}::${row.outcome}`),
  );
  let realizedPnl = new Map<string, number>();
  if (closedRows.length) {
    try {
      realizedPnl = await fetchClosedRealizedPnl(
        resolvedWalletAddress,
        closedRows.map((row) => String(row.condition_id || "")),
      );
    } catch {
      realizedPnl = new Map();
    }
  }

  for (const row of closedRows) {
    const key = `${row.condition_id}::${row.outcome}`;
    const previousSize = safeNumber(row.size);
    const previousValue = safeNumber(row.current_value);
    mergedPositions.push({
      ...row,
      size: 0,
      current_value: 0,
      cash_pnl: null,
      percent_pnl: null,
      realized_pnl: realizedPnl.has(key) ? round(safeNumber(realizedPnl.get(key)), 2) : null,
      previous_size: previousSize,
      previous_current_value: previousValue,
      diff_size: round(-previousSize, 4),
      diff_current_value: round(-previousValue, 2),
      change_status: "closed",
    });
  }

  return {
    walletAddress: resolvedWalletAddress,
    snapshot: current.snapshot,
    compareSnapshot,
    closedSince: closedSince
      ? { id: closedSince.id, snapshot_at: closedSince.snapshot_at }
      : null,
    positions: mergedPositions,
  };
}

// Judge snapshot rows by their state at snapshot time, so markets that resolved
// since then still show up as closed instead of silently disappearing.
function filterHeldAtSnapshot(rows: Record<string, unknown>[]) {
  return rows.filter((row) => isActivePosition(row));
}

// Most recent stored snapshot, skipping the one currently shown (snapshot data mode).
async function getPreviousSnapshot(
  db: D1Database,
  walletAddress: string,
  currentSnapshotId: number | null,
): Promise<Record<string, unknown> | null> {
  const result = await db
    .prepare(
      `
      SELECT id, snapshot_at
      FROM wallet_snapshots
      WHERE wallet_address = ?
      ORDER BY snapshot_at DESC, id DESC
      LIMIT 2
      `,
    )
    .bind(walletAddress)
    .all<Record<string, unknown>>();
  const rows = Array.isArray(result.results) ? result.results : [];
  return rows.find((row) => Number(row.id) !== currentSnapshotId) || null;
}

type ChangeStatus = "new" | "added" | "reduced" | "price" | "unchanged";

// Size changes below 1 share or 0.5% of the previous size are treated as noise.
function classifyChange(
  existedBefore: boolean,
  previousSize: number,
  diffSize: number,
  diffCurrentValue: number,
): ChangeStatus {
  if (!existedBefore) {
    return "new";
  }
  const threshold = Math.max(1, previousSize * 0.005);
  if (diffSize >= threshold) {
    return "added";
  }
  if (diffSize <= -threshold) {
    return "reduced";
  }
  return Math.abs(diffCurrentValue) >= 1 ? "price" : "unchanged";
}

function round(value: number, digits: number): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}


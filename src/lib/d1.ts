export async function getSnapshot(
  db: D1Database,
  snapshotId: number,
): Promise<Record<string, unknown> | null> {
  const result = await db
    .prepare(
      `
      SELECT
        id,
        wallet_address,
        snapshot_at,
        usdc_balance,
        positions_current_value,
        positions_initial_value,
        positions_cash_pnl,
        positions_realized_pnl,
        total_assets,
        positions_count,
        source
      FROM wallet_snapshots
      WHERE id = ?
      LIMIT 1
      `,
    )
    .bind(snapshotId)
    .first<Record<string, unknown>>();

  return result ?? null;
}

export async function getLatestSnapshot(
  db: D1Database,
  walletAddress: string,
): Promise<Record<string, unknown> | null> {
  const result = await db
    .prepare(
      `
      SELECT
        id,
        wallet_address,
        snapshot_at,
        usdc_balance,
        positions_current_value,
        positions_initial_value,
        positions_cash_pnl,
        positions_realized_pnl,
        total_assets,
        positions_count,
        source
      FROM wallet_snapshots
      WHERE wallet_address = ?
      ORDER BY snapshot_at DESC, id DESC
      LIMIT 1
      `,
    )
    .bind(walletAddress)
    .first<Record<string, unknown>>();

  return result ?? null;
}

export async function getSnapshotTokenBalances(
  db: D1Database,
  snapshotId: number,
): Promise<Record<string, unknown>[]> {
  const result = await db
    .prepare(
      `
      SELECT
        id,
        snapshot_id,
        wallet_address,
        chain_id,
        token_symbol,
        token_address,
        decimals,
        balance,
        balance_usd,
        created_at
      FROM wallet_token_balances
      WHERE snapshot_id = ?
      ORDER BY balance_usd DESC, id ASC
      `,
    )
    .bind(snapshotId)
    .all<Record<string, unknown>>();

  return Array.isArray(result.results) ? result.results : [];
}

export async function getSnapshotPositions(
  db: D1Database,
  snapshotId: number,
): Promise<Record<string, unknown>[]> {
  const result = await db
    .prepare(
      `
      SELECT
        id,
        snapshot_id,
        wallet_address,
        condition_id,
        asset,
        opposite_asset,
        title,
        event_slug,
        slug,
        outcome,
        size,
        avg_price,
        cur_price,
        initial_value,
        current_value,
        cash_pnl,
        percent_pnl,
        realized_pnl,
        percent_realized_pnl,
        end_date,
        redeemable,
        mergeable,
        negative_risk,
        created_at
      FROM wallet_positions
      WHERE snapshot_id = ?
      ORDER BY current_value DESC, id ASC
      `,
    )
    .bind(snapshotId)
    .all<Record<string, unknown>>();

  return Array.isArray(result.results) ? result.results : [];
}

export async function createSnapshot(
  db: D1Database,
  params: {
    walletAddress: string;
    snapshotAt: string;
    positionsCount: number;
    positionsInitialValue: number;
    positionsCurrentValue: number;
    positionsCashPnl: number;
    positionsRealizedPnl: number;
    usdcBalance: number;
    totalAssets: number;
    source: string;
  },
): Promise<number> {
  const result = await db
    .prepare(
      `
      INSERT INTO wallet_snapshots (
        wallet_address,
        snapshot_at,
        usdc_balance,
        positions_current_value,
        positions_initial_value,
        positions_cash_pnl,
        positions_realized_pnl,
        total_assets,
        positions_count,
        source
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,
    )
    .bind(
      params.walletAddress,
      params.snapshotAt,
      params.usdcBalance,
      params.positionsCurrentValue,
      params.positionsInitialValue,
      params.positionsCashPnl,
      params.positionsRealizedPnl,
      params.totalAssets,
      params.positionsCount,
      params.source,
    )
    .run();

  // Read the id from the INSERT itself: a separate last_insert_rowid() query is
  // not guaranteed to run on the same connection in D1, and costs a round trip.
  const snapshotId = Number(result.meta?.last_row_id || 0);
  if (!snapshotId) {
    throw new Error("Failed to create snapshot: no row id returned");
  }
  return snapshotId;
}

// D1 batches run as one round trip and one transaction. Chunk to stay well
// under per-request limits for very large wallets.
const BATCH_CHUNK_SIZE = 100;

async function runBatched(db: D1Database, statements: D1PreparedStatement[]): Promise<void> {
  for (let index = 0; index < statements.length; index += BATCH_CHUNK_SIZE) {
    await db.batch(statements.slice(index, index + BATCH_CHUNK_SIZE));
  }
}

export async function insertPositions(
  db: D1Database,
  params: {
    snapshotId: number;
    walletAddress: string;
    positions: Array<Record<string, unknown>>;
  },
): Promise<void> {
  if (!params.positions.length) {
    return;
  }

  const insert = db.prepare(
    `
        INSERT INTO wallet_positions (
          snapshot_id,
          wallet_address,
          condition_id,
          asset,
          opposite_asset,
          title,
          event_slug,
          slug,
          outcome,
          size,
          avg_price,
          cur_price,
          initial_value,
          current_value,
          cash_pnl,
          percent_pnl,
          realized_pnl,
          percent_realized_pnl,
          end_date,
          redeemable,
          mergeable,
          negative_risk
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `,
  );
  const statements = params.positions.map((row) =>
    insert.bind(
      params.snapshotId,
      params.walletAddress,
      row.conditionId,
      row.asset,
      row.oppositeAsset,
      row.title,
      row.eventSlug,
      row.slug,
      row.outcome,
      row.size,
      row.avgPrice,
      row.curPrice,
      row.initialValue,
      row.currentValue,
      row.cashPnl,
      row.percentPnl,
      row.realizedPnl,
      row.percentRealizedPnl,
      row.endDate,
      row.redeemable ? 1 : 0,
      row.mergeable ? 1 : 0,
      row.negativeRisk ? 1 : 0,
    ),
  );
  await runBatched(db, statements);
}

export async function replaceTokenBalance(
  db: D1Database,
  params: {
    snapshotId: number;
    walletAddress: string;
    chainId: number;
    tokenSymbol: string;
    tokenAddress: string;
    decimals: number;
    balance: number;
    balanceUsd: number;
  },
): Promise<void> {
  await db.batch([
    db
      .prepare(
        `
      DELETE FROM wallet_token_balances
      WHERE snapshot_id = ? AND token_address = ?
      `,
      )
      .bind(params.snapshotId, params.tokenAddress),
    db
      .prepare(
      `
      INSERT INTO wallet_token_balances (
        snapshot_id,
        wallet_address,
        chain_id,
        token_symbol,
        token_address,
        decimals,
        balance,
        balance_usd
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `,
    )
    .bind(
      params.snapshotId,
      params.walletAddress,
      params.chainId,
      params.tokenSymbol,
      params.tokenAddress,
      params.decimals,
      params.balance,
      params.balanceUsd,
    ),
  ]);
}

function deleteSnapshotStatements(db: D1Database, snapshotId: number): D1PreparedStatement[] {
  return [
    db.prepare("DELETE FROM wallet_positions WHERE snapshot_id = ?").bind(snapshotId),
    db.prepare("DELETE FROM wallet_token_balances WHERE snapshot_id = ?").bind(snapshotId),
    db.prepare("DELETE FROM wallet_snapshots WHERE id = ?").bind(snapshotId),
  ];
}

export async function pruneOldSnapshots(
  db: D1Database,
  walletAddress: string,
  keep = 100,
): Promise<number> {
  const rows = await db
    .prepare(
      `
      SELECT id
      FROM wallet_snapshots
      WHERE wallet_address = ?
      ORDER BY snapshot_at DESC, id DESC
      LIMIT -1 OFFSET ?
      `,
    )
    .bind(walletAddress, keep)
    .all<{ id: number | string }>();

  const snapshotIds = (rows.results || []).map((row) => Number(row.id)).filter(Boolean);
  if (!snapshotIds.length) {
    return 0;
  }

  await runBatched(
    db,
    snapshotIds.flatMap((snapshotId) => deleteSnapshotStatements(db, snapshotId)),
  );

  return snapshotIds.length;
}

export async function deleteSnapshot(
  db: D1Database,
  snapshotId: number,
): Promise<void> {
  await db.batch(deleteSnapshotStatements(db, snapshotId));
}

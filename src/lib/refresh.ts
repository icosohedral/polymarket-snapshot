import { buildLiveDashboardPayload, fetchLiveData, PrefetchedLiveData } from "./dashboard";
import {
  createSnapshot,
  deleteSnapshot,
  insertPositions,
  pruneOldSnapshots,
  replaceTokenBalance,
} from "./d1";
import { simplifyPosition, summarizePositions } from "./polymarket";
import type { AppEnv } from "./runtime";
import { resolveRuntimeSettings, safeNumber, utcNowIso } from "./runtime";

export async function refreshWalletSnapshot(
  env: AppEnv,
  walletAddress?: string | null,
) {
  const settings = resolveRuntimeSettings(env, walletAddress);
  const live = await fetchLiveData(settings);
  const { usdcResult } = live;
  const positions = live.rows.map(simplifyPosition);
  const summary = summarizePositions(positions);
  const usdcBalance = usdcResult.result ? safeNumber(usdcResult.data) : 0;
  const totalAssets = Math.round((usdcBalance + summary.positionsCurrentValue) * 100) / 100;

  const snapshotId = await createSnapshot(env.DB, {
    walletAddress: settings.walletAddress,
    snapshotAt: utcNowIso(),
    positionsCount: summary.positionsCount,
    positionsInitialValue: summary.positionsInitialValue,
    positionsCurrentValue: summary.positionsCurrentValue,
    positionsCashPnl: summary.positionsCashPnl,
    positionsRealizedPnl: summary.positionsRealizedPnl,
    usdcBalance,
    totalAssets,
    source: "dashboard_refresh",
  });
  try {
    await Promise.all([
      insertPositions(env.DB, {
        snapshotId,
        walletAddress: settings.walletAddress,
        positions,
      }),
      replaceTokenBalance(env.DB, {
        snapshotId,
        walletAddress: settings.walletAddress,
        chainId: settings.chainId,
        tokenSymbol: "pUSD",
        tokenAddress: settings.pusdContractAddress,
        decimals: 6,
        balance: usdcBalance,
        balanceUsd: usdcBalance,
      }),
    ]);
  } catch (error) {
    // Don't leave an empty snapshot behind in history.
    await deleteSnapshot(env.DB, snapshotId).catch(() => undefined);
    throw error;
  }
  const deletedCount = await pruneOldSnapshots(
    env.DB,
    settings.walletAddress,
    settings.retentionLimit,
  );

  return {
    live,
    walletAddress: settings.walletAddress,
    snapshotId,
    positionsCount: positions.length,
    usdcBalance,
    positionsCurrentValue: summary.positionsCurrentValue,
    totalAssets,
    deletedCount,
    usdcResult,
  };
}

export async function runRefresh(
  env: AppEnv,
  walletAddress?: string | null,
) {
  const { live, ...refresh } = await refreshWalletSnapshot(env, walletAddress);
  // Reuse the positions and balance fetched for the snapshot instead of
  // hitting Polymarket and Etherscan a second time.
  const payload = await buildLiveDashboardPayload(
    env,
    walletAddress || refresh.walletAddress,
    live satisfies PrefetchedLiveData,
  );
  return {
    ...payload,
    refresh,
  };
}

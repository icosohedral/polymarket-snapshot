import { buildLiveDashboardPayload } from "./dashboard";
import { deleteSnapshot, getLatestSnapshot, getSnapshot } from "./d1";
import type { AppEnv } from "./runtime";
import { DEFAULT_USER } from "./runtime";

export async function deleteSnapshotForWallet(
  env: AppEnv,
  snapshotId: number,
  walletAddress?: string | null,
) {
  const resolvedWalletAddress = walletAddress || env.POLYMARKET_USER_ADDRESS || DEFAULT_USER;
  const snapshot = await getSnapshot(env.DB, snapshotId);
  if (!snapshot) {
    throw new Error(`Snapshot not found: ${snapshotId}`);
  }
  if (snapshot.wallet_address !== resolvedWalletAddress) {
    throw new Error("Snapshot does not belong to the current wallet");
  }

  const latestSnapshot = await getLatestSnapshot(env.DB, resolvedWalletAddress);
  if (Number(latestSnapshot?.id || 0) === snapshotId) {
    throw new Error("Cannot delete the latest snapshot");
  }

  await deleteSnapshot(env.DB, snapshotId);
  const payload = await buildLiveDashboardPayload(env, resolvedWalletAddress);
  return {
    ...payload,
    deletedSnapshotId: snapshotId,
  };
}

import { deleteSnapshotForWallet } from "../../src/lib/delete-snapshot";
import type { AppEnv } from "../../src/lib/runtime";
import { DEFAULT_USER, safeInt } from "../../src/lib/runtime";

async function handleDeleteSnapshot(context: EventContext<AppEnv, string, unknown>) {
  const url = new URL(context.request.url);
  const walletAddress = url.searchParams.get("wallet");
  const snapshotIdRaw = url.searchParams.get("snapshot_id");
  const snapshotId = safeInt(snapshotIdRaw, 0);

  if (!snapshotId) {
    return Response.json(
      {
        error: "snapshot_id is required",
        walletAddress: walletAddress || context.env.POLYMARKET_USER_ADDRESS || DEFAULT_USER,
        snapshotId: snapshotIdRaw,
      },
      { status: 400 },
    );
  }

  try {
    const payload = await deleteSnapshotForWallet(context.env, snapshotId, walletAddress);
    return Response.json(payload);
  } catch (error) {
    return Response.json(
      {
        error: error instanceof Error ? error.message : "Delete snapshot request failed",
        walletAddress: walletAddress || context.env.POLYMARKET_USER_ADDRESS || DEFAULT_USER,
        snapshotId,
      },
      { status: 500 },
    );
  }
}

export const onRequestPost: PagesFunction<AppEnv> = handleDeleteSnapshot;
export const onRequestGet: PagesFunction<AppEnv> = handleDeleteSnapshot;

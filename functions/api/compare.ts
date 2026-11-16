import { buildComparePayload } from "../../src/lib/compare";
import type { AppEnv } from "../../src/lib/runtime";
import { DEFAULT_USER, safeInt } from "../../src/lib/runtime";

export const onRequestGet: PagesFunction<AppEnv> = async (context) => {
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
    const payload = await buildComparePayload(context.env, snapshotId, walletAddress);
    return Response.json(payload);
  } catch (error) {
    return Response.json(
      {
        error: error instanceof Error ? error.message : "Compare request failed",
        walletAddress: walletAddress || context.env.POLYMARKET_USER_ADDRESS || DEFAULT_USER,
        snapshotId,
      },
      { status: 500 },
    );
  }
};

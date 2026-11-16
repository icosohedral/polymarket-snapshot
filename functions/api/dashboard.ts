import { buildLiveDashboardPayload } from "../../src/lib/dashboard";
import type { AppEnv } from "../../src/lib/runtime";

export const onRequestGet: PagesFunction<AppEnv> = async (context) => {
  const url = new URL(context.request.url);
  const walletAddress = url.searchParams.get("wallet");

  try {
    const payload = await buildLiveDashboardPayload(context.env, walletAddress);
    return Response.json(payload);
  } catch (error) {
    return Response.json(
      {
        error: error instanceof Error ? error.message : "Dashboard request failed",
        walletAddress: walletAddress || context.env.POLYMARKET_USER_ADDRESS || null,
      },
      { status: 500 },
    );
  }
};

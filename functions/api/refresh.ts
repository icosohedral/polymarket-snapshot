import { runRefresh } from "../../src/lib/refresh";
import type { AppEnv } from "../../src/lib/runtime";
import { DEFAULT_USER } from "../../src/lib/runtime";

async function handleRefresh(context: EventContext<AppEnv, string, unknown>) {
  const url = new URL(context.request.url);
  const walletAddress = url.searchParams.get("wallet");

  try {
    const payload = await runRefresh(context.env, walletAddress);
    return Response.json(payload);
  } catch (error) {
    return Response.json(
      {
        error: error instanceof Error ? error.message : "Refresh request failed",
        walletAddress: walletAddress || context.env.POLYMARKET_USER_ADDRESS || DEFAULT_USER,
      },
      { status: 500 },
    );
  }
}

export const onRequestPost: PagesFunction<AppEnv> = handleRefresh;
export const onRequestGet: PagesFunction<AppEnv> = handleRefresh;

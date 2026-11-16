import { safeNumber } from "./runtime";

const ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api";
const ATTEMPT_TIMEOUT_MS = 5_000;

type BalanceParams = {
  apiKey: string;
  userAddress: string;
  pusdContractAddress: string;
  chainId: number;
};

type BalanceResult = { result: boolean; data?: number; error?: string; response?: unknown };

// Etherscan's tokenbalance intermittently answers {"status":"0","message":"NOTOK","result":""}
// for a valid key, so retry and fall back to reading balanceOf directly via eth_call.
export async function getPusdBalance(params: BalanceParams): Promise<BalanceResult> {
  const attempts = [queryTokenBalance, queryBalanceOf, queryTokenBalance];
  let last: BalanceResult = { result: false, error: "Unknown error" };
  for (const attempt of attempts) {
    last = await attempt(params);
    if (last.result) {
      return last;
    }
  }
  return last;
}

async function queryTokenBalance(params: BalanceParams): Promise<BalanceResult> {
  const data = await requestEtherscan(params, {
    module: "account",
    action: "tokenbalance",
    contractaddress: params.pusdContractAddress,
    address: params.userAddress,
    tag: "latest",
  });
  if ("error" in data) {
    return { result: false, error: data.error };
  }
  if (data.body.status === "1" && typeof data.body.result === "string") {
    return { result: true, data: toPusd(safeNumber(data.body.result)) };
  }
  return {
    result: false,
    error: String(data.body.result || data.body.message || "Unknown error"),
    response: data.body,
  };
}

async function queryBalanceOf(params: BalanceParams): Promise<BalanceResult> {
  const holder = params.userAddress.toLowerCase().replace(/^0x/, "").padStart(64, "0");
  const data = await requestEtherscan(params, {
    module: "proxy",
    action: "eth_call",
    to: params.pusdContractAddress,
    data: `0x70a08231${holder}`,
    tag: "latest",
  });
  if ("error" in data) {
    return { result: false, error: data.error };
  }
  const hex = data.body.result;
  if (typeof hex === "string" && /^0x[0-9a-fA-F]+$/.test(hex)) {
    return { result: true, data: toPusd(Number(BigInt(hex))) };
  }
  return { result: false, error: String(hex || data.body.message || "eth_call failed"), response: data.body };
}

async function requestEtherscan(
  params: BalanceParams,
  query: Record<string, string>,
): Promise<{ body: Record<string, unknown> } | { error: string }> {
  const url = new URL(ETHERSCAN_V2_URL);
  url.searchParams.set("chainid", String(params.chainId));
  for (const [key, value] of Object.entries(query)) {
    url.searchParams.set(key, value);
  }
  url.searchParams.set("apikey", params.apiKey);

  try {
    const response = await fetch(url.toString(), { signal: AbortSignal.timeout(ATTEMPT_TIMEOUT_MS) });
    if (!response.ok) {
      return { error: `Etherscan request failed: ${response.status}` };
    }
    return { body: (await response.json()) as Record<string, unknown> };
  } catch (error) {
    return { error: error instanceof Error ? error.message : "Unknown request error" };
  }
}

function toPusd(raw: number): number {
  return Math.round((raw / 1e6) * 100) / 100;
}

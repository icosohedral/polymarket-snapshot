export const DEFAULT_USER = "0x5838192D931f91D2e56893C634aD8861A49C367C";
export const DEFAULT_CHAIN_ID = 137;
export const DEFAULT_PUSD_CONTRACT = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB";
export const DEFAULT_ETHERSCAN_API_KEY = "8ZG7JEK4NKHUTVK5G95MYZV3I6V2CFNDKK";

export type AppEnv = {
  DB: D1Database;
  POLYMARKET_USER_ADDRESS?: string;
  ETHERSCAN_API_KEY?: string;
  PUSD_CONTRACT_ADDRESS?: string;
  USDC_CONTRACT_ADDRESS?: string;
  CHAIN_ID?: string;
  SNAPSHOT_RETENTION?: string;
  DASHBOARD_DATA_MODE?: string;
};

export type RuntimeSettings = {
  walletAddress: string;
  etherscanApiKey: string;
  pusdContractAddress: string;
  chainId: number;
  retentionLimit: number;
  dashboardDataMode: string;
};

export function safeNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function safeInt(value: unknown, fallback = 0): number {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function boolToInt(value: unknown): number {
  return value ? 1 : 0;
}

export function utcNowIso(): string {
  return new Date().toISOString().replace(".000Z", "Z");
}

// Template placeholders such as "replace_me" from .dev.vars.example count as unset.
function realValue(value: string | undefined): string {
  const text = String(value || "").trim();
  return /^(replace[_-]?me|changeme|your[_-].*|xxx+)$/i.test(text) ? "" : text;
}

export function resolveRuntimeSettings(
  env: AppEnv,
  walletAddress?: string | null,
): RuntimeSettings {
  return {
    walletAddress: walletAddress || env.POLYMARKET_USER_ADDRESS || DEFAULT_USER,
    etherscanApiKey: realValue(env.ETHERSCAN_API_KEY) || DEFAULT_ETHERSCAN_API_KEY,
    pusdContractAddress:
      env.PUSD_CONTRACT_ADDRESS || env.USDC_CONTRACT_ADDRESS || DEFAULT_PUSD_CONTRACT,
    chainId: safeInt(env.CHAIN_ID, DEFAULT_CHAIN_ID),
    retentionLimit: safeInt(env.SNAPSHOT_RETENTION, 100),
    dashboardDataMode: String(env.DASHBOARD_DATA_MODE || "live").toLowerCase(),
  };
}

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS wallet_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  wallet_address TEXT NOT NULL,
  snapshot_at TEXT NOT NULL,
  usdc_balance REAL NOT NULL DEFAULT 0,
  positions_current_value REAL NOT NULL DEFAULT 0,
  positions_initial_value REAL NOT NULL DEFAULT 0,
  positions_cash_pnl REAL NOT NULL DEFAULT 0,
  positions_realized_pnl REAL NOT NULL DEFAULT 0,
  total_assets REAL NOT NULL DEFAULT 0,
  positions_count INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'local_seed',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wallet_positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL,
  wallet_address TEXT NOT NULL,
  condition_id TEXT,
  asset TEXT,
  opposite_asset TEXT,
  title TEXT,
  event_slug TEXT,
  slug TEXT,
  outcome TEXT,
  size REAL NOT NULL DEFAULT 0,
  avg_price REAL NOT NULL DEFAULT 0,
  cur_price REAL NOT NULL DEFAULT 0,
  initial_value REAL NOT NULL DEFAULT 0,
  current_value REAL NOT NULL DEFAULT 0,
  cash_pnl REAL NOT NULL DEFAULT 0,
  percent_pnl REAL NOT NULL DEFAULT 0,
  realized_pnl REAL NOT NULL DEFAULT 0,
  percent_realized_pnl REAL NOT NULL DEFAULT 0,
  end_date TEXT,
  redeemable INTEGER NOT NULL DEFAULT 0,
  mergeable INTEGER NOT NULL DEFAULT 0,
  negative_risk INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (snapshot_id) REFERENCES wallet_snapshots(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wallet_token_balances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL,
  wallet_address TEXT NOT NULL,
  chain_id INTEGER NOT NULL,
  token_symbol TEXT NOT NULL,
  token_address TEXT NOT NULL,
  decimals INTEGER NOT NULL DEFAULT 6,
  balance REAL NOT NULL DEFAULT 0,
  balance_usd REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (snapshot_id) REFERENCES wallet_snapshots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_wallet_time
  ON wallet_snapshots(wallet_address, snapshot_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_wallet_positions_snapshot
  ON wallet_positions(snapshot_id, current_value DESC, id ASC);

CREATE INDEX IF NOT EXISTS idx_wallet_token_balances_snapshot
  ON wallet_token_balances(snapshot_id, balance_usd DESC, id ASC);

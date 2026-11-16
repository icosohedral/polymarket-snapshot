#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from typing import Any, Dict, List, Optional, Sequence

import requests

from common import bool_to_int, safe_float, safe_int

DEFAULT_D1_BASE_URL = "https://api.cloudflare.com/client/v4"
MAX_D1_BOUND_PARAMS = 100


class D1Client:
    def __init__(
        self,
        account_id: str,
        database_id: str,
        api_token: str,
        base_url: str = DEFAULT_D1_BASE_URL,
        timeout: int = 15,
    ) -> None:
        self.account_id = account_id
        self.database_id = database_id
        self.timeout = timeout
        self.endpoint = (
            f"{base_url}/accounts/{account_id}/d1/database/{database_id}/query"
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "D1Client":
        d1_config = config.get("d1", {})
        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", d1_config.get("accountId"))
        database_id = os.getenv("CLOUDFLARE_D1_DATABASE_ID", d1_config.get("databaseId"))
        api_token = os.getenv("CLOUDFLARE_API_TOKEN", d1_config.get("apiToken"))
        timeout = safe_int(
            os.getenv("CLOUDFLARE_D1_TIMEOUT", d1_config.get("timeout")),
            15,
        )

        missing = [
            key
            for key, value in (
                ("d1.accountId", account_id),
                ("d1.databaseId", database_id),
                ("d1.apiToken", api_token),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing D1 config: {', '.join(missing)}")

        return cls(
            account_id=account_id,
            database_id=database_id,
            api_token=api_token,
            timeout=timeout,
        )

    def query(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
    ) -> Dict[str, Any]:
        response = self.session.post(
            self.endpoint,
            json={
                "sql": sql,
                "params": [] if params is None else list(params),
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            raise ValueError(f"D1 query failed: {data}")

        result_sets = data.get("result") or []
        if not result_sets:
            raise ValueError(f"D1 query returned no result set: {data}")

        result = result_sets[0]
        if not result.get("success", True):
            raise ValueError(f"D1 query result failed: {data}")

        return result

    def query_results(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
    ) -> List[Dict[str, Any]]:
        return list(self.query(sql, params).get("results") or [])

    def execute(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
    ) -> Dict[str, Any]:
        return self.query(sql, params)

    def create_snapshot(
        self,
        wallet_address: str,
        snapshot_at: str,
        positions_count: int,
        positions_initial_value: float,
        positions_current_value: float,
        positions_cash_pnl: float,
        positions_realized_pnl: float,
        usdc_balance: float = 0,
        total_assets: Optional[float] = None,
        source: str = "polymarket-scan",
    ) -> int:
        if total_assets is None:
            total_assets = round(usdc_balance + positions_current_value, 2)

        result = self.execute(
            """
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
            """,
            [
                wallet_address,
                snapshot_at,
                usdc_balance,
                positions_current_value,
                positions_initial_value,
                positions_cash_pnl,
                positions_realized_pnl,
                total_assets,
                positions_count,
                source,
            ],
        )

        # Each HTTP call may hit a different connection, so prefer the row id
        # returned by the INSERT itself over a separate last_insert_rowid() call.
        last_row_id = safe_int((result.get("meta") or {}).get("last_row_id"))
        if last_row_id:
            return last_row_id

        rows = self.query_results("SELECT last_insert_rowid() AS id")
        if not rows or "id" not in rows[0]:
            raise ValueError("Unable to fetch last_insert_rowid() from D1")
        return safe_int(rows[0]["id"])

    def insert_positions(
        self,
        snapshot_id: int,
        wallet_address: str,
        positions: List[Dict[str, Any]],
    ) -> None:
        if not positions:
            return

        params_per_row = 22
        chunk_size = max(1, MAX_D1_BOUND_PARAMS // params_per_row)
        for start in range(0, len(positions), chunk_size):
            chunk = positions[start : start + chunk_size]
            placeholders: List[str] = []
            params: List[Any] = []

            for row in chunk:
                placeholders.append(
                    "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                )
                params.extend(
                    [
                        snapshot_id,
                        wallet_address,
                        row.get("conditionId"),
                        row.get("asset"),
                        row.get("oppositeAsset"),
                        row.get("title"),
                        row.get("eventSlug"),
                        row.get("slug"),
                        row.get("outcome"),
                        safe_float(row.get("size")),
                        safe_float(row.get("avgPrice")),
                        safe_float(row.get("curPrice")),
                        safe_float(row.get("initialValue")),
                        safe_float(row.get("currentValue")),
                        safe_float(row.get("cashPnl")),
                        safe_float(row.get("percentPnl")),
                        safe_float(row.get("realizedPnl")),
                        safe_float(row.get("percentRealizedPnl")),
                        row.get("endDate"),
                        bool_to_int(row.get("redeemable")),
                        bool_to_int(row.get("mergeable")),
                        bool_to_int(row.get("negativeRisk")),
                    ]
                )

            self.execute(
                f"""
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
                ) VALUES {", ".join(placeholders)}
                """,
                params,
            )

    def get_latest_snapshot(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        rows = self.query_results(
            """
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
            """,
            [wallet_address],
        )
        return rows[0] if rows else None

    def get_snapshot(self, snapshot_id: int) -> Optional[Dict[str, Any]]:
        rows = self.query_results(
            """
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
            """,
            [snapshot_id],
        )
        return rows[0] if rows else None

    def update_snapshot_balances(
        self,
        snapshot_id: int,
        usdc_balance: float,
        total_assets: float,
    ) -> None:
        self.execute(
            """
            UPDATE wallet_snapshots
            SET usdc_balance = ?, total_assets = ?
            WHERE id = ?
            """,
            [usdc_balance, total_assets, snapshot_id],
        )

    def replace_token_balance(
        self,
        snapshot_id: int,
        wallet_address: str,
        chain_id: int,
        token_symbol: str,
        token_address: str,
        decimals: int,
        balance: float,
        balance_usd: Optional[float] = None,
    ) -> None:
        self.execute(
            """
            DELETE FROM wallet_token_balances
            WHERE snapshot_id = ? AND token_address = ?
            """,
            [snapshot_id, token_address],
        )
        self.execute(
            """
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
            """,
            [
                snapshot_id,
                wallet_address,
                chain_id,
                token_symbol,
                token_address,
                decimals,
                balance,
                balance_usd,
            ],
        )

    def prune_old_snapshots(self, wallet_address: str, keep: int = 100) -> int:
        rows = self.query_results(
            """
            SELECT id
            FROM wallet_snapshots
            WHERE wallet_address = ?
            ORDER BY snapshot_at DESC, id DESC
            LIMIT -1 OFFSET ?
            """,
            [wallet_address, keep],
        )
        snapshot_ids = [safe_int(row.get("id")) for row in rows if row.get("id") is not None]
        if not snapshot_ids:
            return 0

        chunk_size = 50
        for start in range(0, len(snapshot_ids), chunk_size):
            chunk = snapshot_ids[start : start + chunk_size]
            placeholders = ", ".join(["?"] * len(chunk))
            self.execute(
                f"DELETE FROM wallet_positions WHERE snapshot_id IN ({placeholders})",
                chunk,
            )
            self.execute(
                f"DELETE FROM wallet_token_balances WHERE snapshot_id IN ({placeholders})",
                chunk,
            )
            self.execute(
                f"DELETE FROM wallet_snapshots WHERE id IN ({placeholders})",
                chunk,
            )

        return len(snapshot_ids)

    def delete_snapshot(self, snapshot_id: int) -> None:
        self.execute(
            "DELETE FROM wallet_positions WHERE snapshot_id = ?",
            [snapshot_id],
        )
        self.execute(
            "DELETE FROM wallet_token_balances WHERE snapshot_id = ?",
            [snapshot_id],
        )
        self.execute(
            "DELETE FROM wallet_snapshots WHERE id = ?",
            [snapshot_id],
        )

    def get_snapshot_positions(self, snapshot_id: int) -> List[Dict[str, Any]]:
        return self.query_results(
            """
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
            """,
            [snapshot_id],
        )

    def get_snapshot_token_balances(self, snapshot_id: int) -> List[Dict[str, Any]]:
        return self.query_results(
            """
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
            ORDER BY token_symbol ASC, id ASC
            """,
            [snapshot_id],
        )

    def get_latest_dashboard_data(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        snapshot = self.get_latest_snapshot(wallet_address)
        if snapshot is None:
            return None

        snapshot_id = safe_int(snapshot.get("id"))
        return {
            "snapshot": snapshot,
            "positions": self.get_snapshot_positions(snapshot_id),
            "tokenBalances": self.get_snapshot_token_balances(snapshot_id),
        }

    def get_snapshot_history(
        self,
        wallet_address: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        return self.query_results(
            """
            SELECT
              id,
              snapshot_at,
              usdc_balance,
              positions_current_value,
              positions_cash_pnl,
              total_assets,
              positions_count
            FROM wallet_snapshots
            WHERE wallet_address = ?
            ORDER BY snapshot_at DESC, id DESC
            LIMIT ?
            """,
            [wallet_address, limit],
        )

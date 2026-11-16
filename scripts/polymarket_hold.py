#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from typing import Any, Dict, List, Optional

import requests

from common import DEFAULT_USER, load_config, summarize_positions, utc_now_iso
from d1_client import D1Client
from wallet_scan import DEFAULT_CHAIN_ID, DEFAULT_ETHERSCAN_API_KEY, DEFAULT_PUSD_CONTRACT, get_pusd_balance

POLYMARKET_POSITIONS_URL = "https://data-api.polymarket.com/v2/positions"


class PolymarketPositionsSpider:
    def __init__(
        self,
        user_address: str = DEFAULT_USER,
        page_limit: int = 100,
        timeout: int = 10,
        sleep_seconds: float = 0.2,
    ) -> None:
        self.user_address = user_address
        self.page_limit = page_limit
        self.timeout = timeout
        self.sleep_seconds = sleep_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/146.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
            }
        )

    def fetch_page(
        self,
        cursor: Optional[str] = None,
        sort_by: str = "CURRENT_VALUE",
        sort_direction: str = "DESC",
        size_threshold: float = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "user": self.user_address,
            "limit": self.page_limit,
            "sortBy": sort_by,
            "sortDirection": sort_direction,
            "sizeThreshold": size_threshold,
        }
        if cursor:
            params["cursor"] = cursor

        resp = self.session.get(
            POLYMARKET_POSITIONS_URL,
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ValueError(f"Unexpected response format: {type(data)}")

        return data

    def fetch_all_positions(
        self,
        sort_by: str = "CURRENT_VALUE",
        sort_direction: str = "DESC",
        size_threshold: float = 0,
    ) -> List[Dict[str, Any]]:
        # Data API v2: cursor-based pagination, response is {data, pagination}.
        all_rows: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        for _ in range(1000):
            body = self.fetch_page(
                cursor=cursor,
                sort_by=sort_by,
                sort_direction=sort_direction,
                size_threshold=size_threshold,
            )
            all_rows.extend(body["data"])

            pagination = body.get("pagination") or {}
            cursor = pagination.get("next_cursor")
            if not pagination.get("has_more") or not cursor:
                break
            time.sleep(self.sleep_seconds)

        return all_rows

    @staticmethod
    def simplify_position(row: Dict[str, Any]) -> Dict[str, Any]:
        # Map Data API v2 (snake_case) rows to the legacy v1 shape stored in D1.
        return {
            "title": row.get("title"),
            "outcome": row.get("outcome"),
            "size": row.get("current_size"),
            "avgPrice": row.get("avg_price"),
            "curPrice": row.get("current_price"),
            "initialValue": row.get("entry_cost_usdc"),
            "currentValue": row.get("current_value"),
            "cashPnl": row.get("unrealized_pnl"),
            "percentPnl": row.get("percent_pnl"),
            "realizedPnl": row.get("realized_pnl"),
            "percentRealizedPnl": row.get("percent_realized_pnl"),
            "slug": row.get("slug"),
            "eventSlug": row.get("event_slug"),
            "conditionId": row.get("condition_id"),
            "asset": row.get("token_id"),
            "oppositeAsset": row.get("opposite_token_id"),
            "endDate": row.get("end_date"),
            "redeemable": row.get("redeemable"),
            "mergeable": row.get("mergeable"),
            "negativeRisk": row.get("negative_risk"),
        }

def main() -> None:
    config = load_config()
    user_address = os.getenv(
        "POLYMARKET_USER_ADDRESS",
        config.get("userAddress", DEFAULT_USER),
    )
    etherscan_api_key = os.getenv(
        "ETHERSCAN_API_KEY",
        config.get("etherscanApiKey", DEFAULT_ETHERSCAN_API_KEY),
    )
    pusd_contract_address = os.getenv(
        "PUSD_CONTRACT_ADDRESS",
        os.getenv(
            "USDC_CONTRACT_ADDRESS",
            config.get("pusdContractAddress", config.get("usdcContractAddress", DEFAULT_PUSD_CONTRACT)),
        ),
    )
    chain_id = int(os.getenv("CHAIN_ID", str(config.get("chainId", DEFAULT_CHAIN_ID))))
    retention_limit = int(os.getenv("SNAPSHOT_RETENTION", str(config.get("snapshotRetention", 100))))

    spider = PolymarketPositionsSpider(
        user_address=user_address,
        page_limit=100,
        timeout=10,
        sleep_seconds=0.2,
    )

    rows = spider.fetch_all_positions(
        sort_by="CURRENT_VALUE",  # Data API v2 排序字段
        sort_direction="DESC",
        size_threshold=0,         # 设成 1 可过滤很小仓位
    )

    simplified = [spider.simplify_position(r) for r in rows]
    summary = summarize_positions(simplified)
    snapshot_at = utc_now_iso()
    pusd_result = get_pusd_balance(
        api_key=etherscan_api_key,
        user_address=user_address,
        pusd_contract_address=pusd_contract_address,
        chain_id=chain_id,
    )
    pusd_balance = pusd_result["data"] if pusd_result.get("result") else 0.0
    total_assets = round(pusd_balance + summary["positionsCurrentValue"], 2)

    d1 = D1Client.from_config(config)
    snapshot_id = d1.create_snapshot(
        wallet_address=user_address,
        snapshot_at=snapshot_at,
        positions_count=summary["positionsCount"],
        positions_initial_value=summary["positionsInitialValue"],
        positions_current_value=summary["positionsCurrentValue"],
        positions_cash_pnl=summary["positionsCashPnl"],
        positions_realized_pnl=summary["positionsRealizedPnl"],
        usdc_balance=pusd_balance,
        total_assets=total_assets,
        source="polymarket_positions",
    )
    d1.insert_positions(
        snapshot_id=snapshot_id,
        wallet_address=user_address,
        positions=simplified,
    )
    d1.replace_token_balance(
        snapshot_id=snapshot_id,
        wallet_address=user_address,
        chain_id=chain_id,
        token_symbol="pUSD",
        token_address=pusd_contract_address,
        decimals=6,
        balance=pusd_balance,
        balance_usd=pusd_balance,
    )
    deleted_count = d1.prune_old_snapshots(
        wallet_address=user_address,
        keep=retention_limit,
    )

    print(f"抓取完成，共 {len(rows)} 条持仓。")
    print(f"已写入 D1: snapshot_id={snapshot_id}")
    if deleted_count:
        print(f"已清理旧快照: {deleted_count} 条")
    print(
        "持仓汇总: "
        f"currentValue={summary['positionsCurrentValue']} | "
        f"pusdBalance={pusd_balance} | "
        f"totalAssets={total_assets} | "
        f"cashPnl={summary['positionsCashPnl']} | "
        f"realizedPnl={summary['positionsRealizedPnl']}"
    )

    print("\n前 10 条持仓示例:")
    for i, row in enumerate(simplified[:10], start=1):
        print(
            f"{i:>2}. {row['title']} | {row['outcome']} | "
            f"size={row['size']} | curValue={row['currentValue']} | pnl={row['cashPnl']}"
        )


if __name__ == "__main__":
    main()

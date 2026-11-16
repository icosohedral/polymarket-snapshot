#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from typing import Any, Dict, List, Optional

from common import DEFAULT_USER, bool_to_int, load_config, safe_int, summarize_positions, utc_now_iso
from d1_client import D1Client
from polymarket_hold import PolymarketPositionsSpider
from wallet_scan import (
    DEFAULT_CHAIN_ID,
    DEFAULT_ETHERSCAN_API_KEY,
    DEFAULT_PUSD_CONTRACT,
    get_pusd_balance,
)


def debug_log(message: str, **fields: Any) -> None:
    details = " ".join(f"{key}={fields[key]!r}" for key in sorted(fields))
    if details:
        print(f"[snapshot_refresh] {message} {details}")
    else:
        print(f"[snapshot_refresh] {message}")


def resolve_runtime_settings(
    config: Dict[str, Any],
    wallet_address: Optional[str] = None,
) -> Dict[str, Any]:
    def env_or_config(name: str, fallback: Any) -> Any:
        value = os.getenv(name)
        return fallback if value in (None, "") else value

    resolved_wallet = wallet_address or env_or_config(
        "POLYMARKET_USER_ADDRESS",
        config.get("userAddress", DEFAULT_USER),
    )
    etherscan_api_key = env_or_config(
        "ETHERSCAN_API_KEY",
        config.get("etherscanApiKey", DEFAULT_ETHERSCAN_API_KEY),
    )
    pusd_contract_address = env_or_config(
        "PUSD_CONTRACT_ADDRESS",
        env_or_config(
            "USDC_CONTRACT_ADDRESS",
            config.get("pusdContractAddress", config.get("usdcContractAddress", DEFAULT_PUSD_CONTRACT)),
        ),
    )
    chain_id = safe_int(
        env_or_config("CHAIN_ID", config.get("chainId", DEFAULT_CHAIN_ID)),
        DEFAULT_CHAIN_ID,
    )
    retention_limit = safe_int(
        env_or_config("SNAPSHOT_RETENTION", config.get("snapshotRetention", 100)),
        100,
    )

    return {
        "walletAddress": resolved_wallet,
        "etherscanApiKey": etherscan_api_key,
        "pusdContractAddress": pusd_contract_address,
        "chainId": chain_id,
        "retentionLimit": retention_limit,
    }


def normalize_position_for_dashboard(
    position: Dict[str, Any],
    wallet_address: str,
    snapshot_id: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "id": None,
        "snapshot_id": snapshot_id,
        "wallet_address": wallet_address,
        "condition_id": position.get("conditionId"),
        "asset": position.get("asset"),
        "opposite_asset": position.get("oppositeAsset"),
        "title": position.get("title"),
        "event_slug": position.get("eventSlug"),
        "slug": position.get("slug"),
        "outcome": position.get("outcome"),
        "size": position.get("size"),
        "avg_price": position.get("avgPrice"),
        "cur_price": position.get("curPrice"),
        "initial_value": position.get("initialValue"),
        "current_value": position.get("currentValue"),
        "cash_pnl": position.get("cashPnl"),
        "percent_pnl": position.get("percentPnl"),
        "realized_pnl": position.get("realizedPnl"),
        "percent_realized_pnl": position.get("percentRealizedPnl"),
        "end_date": position.get("endDate"),
        "redeemable": bool_to_int(position.get("redeemable")),
        "mergeable": bool_to_int(position.get("mergeable")),
        "negative_risk": bool_to_int(position.get("negativeRisk")),
        "created_at": None,
    }


def collect_wallet_snapshot_data(
    wallet_address: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    source: str = "live_dashboard",
) -> Dict[str, Any]:
    config = config or load_config()
    settings = resolve_runtime_settings(config, wallet_address)
    debug_log("start", wallet=settings["walletAddress"], chain_id=settings["chainId"], source=source)

    spider = PolymarketPositionsSpider(
        user_address=settings["walletAddress"],
        page_limit=100,
        timeout=10,
        sleep_seconds=0.2,
    )
    rows = spider.fetch_all_positions(
        sort_by="CURRENT_VALUE",
        sort_direction="DESC",
        size_threshold=0,
    )
    debug_log("positions_fetched", rows=len(rows), source=source)
    positions = [spider.simplify_position(row) for row in rows]
    dashboard_positions = [
        normalize_position_for_dashboard(position, wallet_address=settings["walletAddress"])
        for position in positions
    ]
    summary = summarize_positions(positions)
    debug_log(
        "positions_summarized",
        positions_count=summary["positionsCount"],
        current_value=summary["positionsCurrentValue"],
        cash_pnl=summary["positionsCashPnl"],
        source=source,
    )

    pusd_result = get_pusd_balance(
        api_key=settings["etherscanApiKey"],
        user_address=settings["walletAddress"],
        pusd_contract_address=settings["pusdContractAddress"],
        chain_id=settings["chainId"],
    )
    pusd_balance = pusd_result["data"] if pusd_result.get("result") else 0.0
    total_assets = round(pusd_balance + summary["positionsCurrentValue"], 2)
    snapshot = {
        "id": None,
        "wallet_address": settings["walletAddress"],
        "snapshot_at": utc_now_iso(),
        "usdc_balance": pusd_balance,
        "positions_current_value": summary["positionsCurrentValue"],
        "positions_initial_value": summary["positionsInitialValue"],
        "positions_cash_pnl": summary["positionsCashPnl"],
        "positions_realized_pnl": summary["positionsRealizedPnl"],
        "total_assets": total_assets,
        "positions_count": summary["positionsCount"],
        "source": source,
    }
    debug_log(
        "pusd_fetched",
        success=bool(pusd_result.get("result")),
        pusd_balance=pusd_balance,
        error=pusd_result.get("error"),
        source=source,
    )

    return {
        "settings": settings,
        "snapshot": snapshot,
        "positions": positions,
        "dashboardPositions": dashboard_positions,
        "summary": summary,
        "usdcBalance": pusd_balance,
        "usdcResult": pusd_result,
        "totalAssets": total_assets,
    }


def build_live_dashboard_payload(
    wallet_address: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    config = config or load_config()
    live_data = collect_wallet_snapshot_data(wallet_address=wallet_address, config=config)
    d1 = D1Client.from_config(config)
    wallet = live_data["settings"]["walletAddress"]
    history = d1.get_snapshot_history(wallet, limit=20)

    return {
        "walletAddress": wallet,
        "snapshot": live_data["snapshot"],
        "positions": live_data["dashboardPositions"],
        "tokenBalances": [],
        "history": history,
        "live": {
            "usdcResult": live_data["usdcResult"],
            "source": live_data["snapshot"]["source"],
        },
    }


def refresh_wallet_snapshot(
    wallet_address: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    config = config or load_config()
    live_data = collect_wallet_snapshot_data(
        wallet_address=wallet_address,
        config=config,
        source="dashboard_refresh",
    )
    settings = live_data["settings"]
    positions = live_data["positions"]
    summary = live_data["summary"]
    usdc_balance = live_data["usdcBalance"]
    usdc_result = live_data["usdcResult"]
    total_assets = live_data["totalAssets"]

    d1 = D1Client.from_config(config)
    snapshot_id = d1.create_snapshot(
        wallet_address=settings["walletAddress"],
        snapshot_at=utc_now_iso(),
        positions_count=summary["positionsCount"],
        positions_initial_value=summary["positionsInitialValue"],
        positions_current_value=summary["positionsCurrentValue"],
        positions_cash_pnl=summary["positionsCashPnl"],
        positions_realized_pnl=summary["positionsRealizedPnl"],
        usdc_balance=usdc_balance,
        total_assets=total_assets,
        source="dashboard_refresh",
    )
    debug_log("snapshot_created", snapshot_id=snapshot_id, total_assets=total_assets)
    d1.insert_positions(
        snapshot_id=snapshot_id,
        wallet_address=settings["walletAddress"],
        positions=positions,
    )
    debug_log("positions_inserted", snapshot_id=snapshot_id, rows=len(positions))
    d1.replace_token_balance(
        snapshot_id=snapshot_id,
        wallet_address=settings["walletAddress"],
        chain_id=settings["chainId"],
        token_symbol="pUSD",
        token_address=settings["pusdContractAddress"],
        decimals=6,
        balance=usdc_balance,
        balance_usd=usdc_balance,
    )
    deleted_count = d1.prune_old_snapshots(
        wallet_address=settings["walletAddress"],
        keep=settings["retentionLimit"],
    )
    debug_log("done", snapshot_id=snapshot_id, deleted_count=deleted_count)

    return {
        "walletAddress": settings["walletAddress"],
        "snapshotId": snapshot_id,
        "positionsCount": len(positions),
        "usdcBalance": usdc_balance,
        "positionsCurrentValue": summary["positionsCurrentValue"],
        "totalAssets": total_assets,
        "deletedCount": deleted_count,
        "usdcResult": usdc_result,
    }


def main() -> None:
    result = refresh_wallet_snapshot()
    print(
        "snapshot_refresh_done "
        f"wallet={result['walletAddress']} "
        f"snapshot_id={result['snapshotId']} "
        f"positions={result['positionsCount']} "
        f"total_assets={result['totalAssets']}"
    )


if __name__ == "__main__":
    main()

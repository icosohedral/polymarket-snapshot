#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from typing import Any, Dict

import requests

from common import DEFAULT_USER, load_config, safe_float, utc_now_iso
from d1_client import D1Client

ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api"
DEFAULT_CHAIN_ID = 137
DEFAULT_PUSD_CONTRACT = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"
DEFAULT_ETHERSCAN_API_KEY = "8ZG7JEK4NKHUTVK5G95MYZV3I6V2CFNDKK"


def get_pusd_balance(
    api_key: str,
    user_address: str,
    pusd_contract_address: str = DEFAULT_PUSD_CONTRACT,
    chain_id: int = DEFAULT_CHAIN_ID,
    timeout: int = 5,
) -> Dict[str, Any]:
    """Etherscan's tokenbalance intermittently answers NOTOK with an empty result for a
    valid key, so retry and fall back to reading balanceOf directly via eth_call."""
    holder = user_address.lower().replace("0x", "").rjust(64, "0")
    attempts = [
        {"module": "account", "action": "tokenbalance",
         "contractaddress": pusd_contract_address, "address": user_address},
        {"module": "proxy", "action": "eth_call",
         "to": pusd_contract_address, "data": "0x70a08231" + holder},
        {"module": "account", "action": "tokenbalance",
         "contractaddress": pusd_contract_address, "address": user_address},
    ]
    last: Dict[str, Any] = {"result": False, "error": "Unknown error"}
    for query in attempts:
        params = {**query, "tag": "latest", "chainid": chain_id, "apikey": api_key}
        try:
            response = requests.get(ETHERSCAN_V2_URL, params=params, timeout=timeout)
            response.raise_for_status()
            result = response.json()
        except (requests.exceptions.RequestException, ValueError) as exc:
            last = {"result": False, "error": str(exc)}
            continue

        value = result.get("result")
        if query["action"] == "eth_call":
            if isinstance(value, str) and re.fullmatch(r"0x[0-9a-fA-F]+", value):
                return {"result": True, "data": round(int(value, 16) / 1e6, 2)}
        elif result.get("status") == "1":
            return {"result": True, "data": round(int(value) / 1e6, 2)}

        last = {
            "result": False,
            "error": value or result.get("message") or "Unknown error",
            "response": result,
        }
    return last


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
    chain_id = int(
        os.getenv(
            "CHAIN_ID",
            str(config.get("chainId", DEFAULT_CHAIN_ID)),
        )
    )
    retention_limit = int(
        os.getenv(
            "SNAPSHOT_RETENTION",
            str(config.get("snapshotRetention", 100)),
        )
    )

    pusd_result = get_pusd_balance(
        api_key=etherscan_api_key,
        user_address=user_address,
        pusd_contract_address=pusd_contract_address,
        chain_id=chain_id,
    )
    pusd_balance = pusd_result["data"] if pusd_result["result"] else 0.0
    d1 = D1Client.from_config(config)
    latest_snapshot = d1.get_latest_snapshot(user_address)

    if latest_snapshot:
        snapshot_id = int(latest_snapshot["id"])
        positions_current_value = safe_float(latest_snapshot.get("positions_current_value"))
        total_assets = round(pusd_balance + positions_current_value, 2)
        d1.update_snapshot_balances(
            snapshot_id=snapshot_id,
            usdc_balance=pusd_balance,
            total_assets=total_assets,
        )
    else:
        snapshot_id = d1.create_snapshot(
            wallet_address=user_address,
            snapshot_at=utc_now_iso(),
            positions_count=0,
            positions_initial_value=0,
            positions_current_value=0,
            positions_cash_pnl=0,
            positions_realized_pnl=0,
            usdc_balance=pusd_balance,
            total_assets=pusd_balance,
            source="wallet_scan_only",
        )
        total_assets = pusd_balance
        positions_current_value = 0

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

    if pusd_result["result"]:
        print(f"pUSD 余额: {pusd_balance}")
    else:
        print(f"pUSD 查询失败: {pusd_result['error']}")

    print(
        "总资产汇总: "
        f"pUSD={pusd_balance} | "
        f"持仓市值={positions_current_value} | "
        f"总资产={total_assets}"
    )
    print(f"已写入 D1: snapshot_id={snapshot_id}")
    if deleted_count:
        print(f"已清理旧快照: {deleted_count} 条")


if __name__ == "__main__":
    main()

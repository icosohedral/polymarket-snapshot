#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

DEFAULT_CONFIG_FILE = "config.json"
DEFAULT_USER = "0x5838192D931f91D2e56893C634aD8861A49C367C"


def load_config(filepath: str = DEFAULT_CONFIG_FILE) -> Dict[str, Any]:
    if not os.path.exists(filepath):
        return {}

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Unexpected config format: {type(data)}")

    return data


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def bool_to_int(value: Any) -> int:
    return 1 if bool(value) else 0


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def summarize_positions(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_initial_value = round(
        sum(safe_float(row.get("initialValue")) for row in positions), 2
    )
    total_current_value = round(
        sum(safe_float(row.get("currentValue")) for row in positions), 2
    )
    total_cash_pnl = round(sum(safe_float(row.get("cashPnl")) for row in positions), 2)
    total_realized_pnl = round(
        sum(safe_float(row.get("realizedPnl")) for row in positions), 2
    )

    return {
        "positionsCount": len(positions),
        "positionsInitialValue": total_initial_value,
        "positionsCurrentValue": total_current_value,
        "positionsCashPnl": total_cash_pnl,
        "positionsRealizedPnl": total_realized_pnl,
    }

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse
from datetime import date

from common import DEFAULT_USER, load_config, safe_float
from d1_client import D1Client
from snapshot_refresh import build_live_dashboard_payload, refresh_wallet_snapshot

HOST = "127.0.0.1"
PORT = 8000
BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "dashboard.html"


def debug_log(message: str, **fields: Any) -> None:
    details = " ".join(f"{key}={fields[key]!r}" for key in sorted(fields))
    if details:
        print(f"[dashboard_server] {message} {details}")
    else:
        print(f"[dashboard_server] {message}")


def is_active_position(position: Dict[str, Any]) -> bool:
    if int(position.get("redeemable") or 0) == 1:
        return False

    if safe_float(position.get("current_value")) < 1:
        return False

    end_date = position.get("end_date")
    if isinstance(end_date, str) and end_date:
        try:
            if date.fromisoformat(end_date) < date.today():
                return False
        except ValueError:
            pass

    return True


def build_dashboard_payload(wallet_address: str) -> Dict[str, Any]:
    config = load_config()
    data = build_live_dashboard_payload(wallet_address=wallet_address, config=config)
    if data.get("snapshot") is None:
        debug_log("dashboard_payload_empty", wallet=wallet_address)
        return data
    data["positions"] = [row for row in data["positions"] if is_active_position(row)]
    data["walletAddress"] = wallet_address
    debug_log(
        "dashboard_payload_ready",
        wallet=wallet_address,
        snapshot_id=data["snapshot"].get("id"),
        positions=len(data["positions"]),
        history=len(data["history"]),
    )
    return data


def build_compare_payload(wallet_address: str, compare_snapshot_id: int) -> Dict[str, Any]:
    config = load_config()
    current = build_live_dashboard_payload(wallet_address=wallet_address, config=config)
    d1 = D1Client.from_config(config)
    if current.get("snapshot") is None:
        return {
            "walletAddress": wallet_address,
            "snapshot": None,
            "compareSnapshot": None,
            "positions": [],
        }

    compare_snapshot = d1.get_snapshot(compare_snapshot_id)
    if compare_snapshot is None:
        raise ValueError(f"Snapshot not found: {compare_snapshot_id}")

    if compare_snapshot.get("wallet_address") != wallet_address:
        raise ValueError("Snapshot does not belong to the current wallet")

    latest_positions = [row for row in current["positions"] if is_active_position(row)]
    compare_positions = [
        row for row in d1.get_snapshot_positions(compare_snapshot_id) if is_active_position(row)
    ]
    compare_map = {
        f"{row.get('condition_id')}::{row.get('outcome')}": row
        for row in compare_positions
    }

    merged_positions = []
    for row in latest_positions:
        key = f"{row.get('condition_id')}::{row.get('outcome')}"
        previous = compare_map.get(key, {})
        current_size = safe_float(row.get("size"))
        current_value = safe_float(row.get("current_value"))
        merged_row = dict(row)
        merged_row["diff_size"] = round(current_size - safe_float(previous.get("size")), 4)
        merged_row["diff_current_value"] = round(
            current_value - safe_float(previous.get("current_value")),
            2,
        )
        merged_positions.append(merged_row)

    return {
        "walletAddress": wallet_address,
        "snapshot": current["snapshot"],
        "compareSnapshot": compare_snapshot,
        "positions": merged_positions,
    }


def run_refresh(wallet_address: str, config: Dict[str, Any]) -> Dict[str, Any]:
    refresh_result = refresh_wallet_snapshot(wallet_address=wallet_address, config=config)
    payload = build_live_dashboard_payload(wallet_address=wallet_address, config=config)
    payload["positions"] = [row for row in payload["positions"] if is_active_position(row)]
    payload["refresh"] = refresh_result
    return payload


def delete_snapshot_for_wallet(wallet_address: str, snapshot_id: int) -> Dict[str, Any]:
    config = load_config()
    d1 = D1Client.from_config(config)
    snapshot = d1.get_snapshot(snapshot_id)
    if snapshot is None:
        raise ValueError(f"Snapshot not found: {snapshot_id}")
    if snapshot.get("wallet_address") != wallet_address:
        raise ValueError("Snapshot does not belong to the current wallet")

    latest_snapshot = d1.get_latest_snapshot(wallet_address)
    if latest_snapshot and int(latest_snapshot.get("id") or 0) == snapshot_id:
        raise ValueError("Cannot delete the latest snapshot")

    d1.delete_snapshot(snapshot_id)
    payload = build_dashboard_payload(wallet_address)
    payload["deletedSnapshotId"] = snapshot_id
    return payload


class DashboardHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self) -> None:
        body = HTML_FILE.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/dashboard.html"):
            self._send_html()
            return

        if parsed.path == "/api/dashboard":
            config = load_config()
            query = parse_qs(parsed.query)
            wallet_address = query.get("wallet", [config.get("userAddress", DEFAULT_USER)])[0]
            debug_log("api_dashboard_request", wallet=wallet_address, path=self.path)
            try:
                payload = build_dashboard_payload(wallet_address)
                self._send_json(200, payload)
            except Exception as exc:
                debug_log("api_dashboard_error", wallet=wallet_address, error=str(exc))
                self._send_json(
                    500,
                    {
                        "error": str(exc),
                        "walletAddress": wallet_address,
                    },
                )
            return

        if parsed.path == "/api/compare":
            config = load_config()
            query = parse_qs(parsed.query)
            wallet_address = query.get("wallet", [config.get("userAddress", DEFAULT_USER)])[0]
            snapshot_id_raw = query.get("snapshot_id", [""])[0]
            debug_log(
                "api_compare_request",
                wallet=wallet_address,
                snapshot_id=snapshot_id_raw,
                path=self.path,
            )
            try:
                snapshot_id = int(snapshot_id_raw)
                payload = build_compare_payload(wallet_address, snapshot_id)
                self._send_json(200, payload)
            except Exception as exc:
                debug_log(
                    "api_compare_error",
                    wallet=wallet_address,
                    snapshot_id=snapshot_id_raw,
                    error=str(exc),
                )
                self._send_json(
                    500,
                    {
                        "error": str(exc),
                        "walletAddress": wallet_address,
                        "snapshotId": snapshot_id_raw,
                    },
                )
            return

        if parsed.path == "/api/refresh":
            config = load_config()
            query = parse_qs(parsed.query)
            wallet_address = query.get("wallet", [config.get("userAddress", DEFAULT_USER)])[0]
            debug_log("api_refresh_request_get", wallet=wallet_address, path=self.path)
            try:
                payload = run_refresh(wallet_address, config)
                debug_log(
                    "api_refresh_success_get",
                    wallet=wallet_address,
                    snapshot_id=payload.get("refresh", {}).get("snapshotId"),
                    positions=payload.get("refresh", {}).get("positionsCount"),
                )
                self._send_json(200, payload)
            except Exception as exc:
                debug_log("api_refresh_error_get", wallet=wallet_address, error=str(exc))
                self._send_json(
                    500,
                    {
                        "error": str(exc),
                        "walletAddress": wallet_address,
                    },
                )
            return

        if parsed.path == "/api/delete-snapshot":
            config = load_config()
            query = parse_qs(parsed.query)
            wallet_address = query.get("wallet", [config.get("userAddress", DEFAULT_USER)])[0]
            snapshot_id_raw = query.get("snapshot_id", [""])[0]
            debug_log(
                "api_delete_snapshot_request_get",
                wallet=wallet_address,
                snapshot_id=snapshot_id_raw,
                path=self.path,
            )
            try:
                snapshot_id = int(snapshot_id_raw)
                payload = delete_snapshot_for_wallet(wallet_address, snapshot_id)
                debug_log(
                    "api_delete_snapshot_success_get",
                    wallet=wallet_address,
                    snapshot_id=snapshot_id,
                )
                self._send_json(200, payload)
            except Exception as exc:
                debug_log(
                    "api_delete_snapshot_error_get",
                    wallet=wallet_address,
                    snapshot_id=snapshot_id_raw,
                    error=str(exc),
                )
                self._send_json(
                    500,
                    {
                        "error": str(exc),
                        "walletAddress": wallet_address,
                        "snapshotId": snapshot_id_raw,
                    },
                )
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/refresh":
            config = load_config()
            query = parse_qs(parsed.query)
            wallet_address = query.get("wallet", [config.get("userAddress", DEFAULT_USER)])[0]
            debug_log("api_refresh_request", wallet=wallet_address, path=self.path)
            try:
                payload = run_refresh(wallet_address, config)
                debug_log(
                    "api_refresh_success",
                    wallet=wallet_address,
                    snapshot_id=payload.get("refresh", {}).get("snapshotId"),
                    positions=payload.get("refresh", {}).get("positionsCount"),
                )
                self._send_json(200, payload)
            except Exception as exc:
                debug_log("api_refresh_error", wallet=wallet_address, error=str(exc))
                self._send_json(
                    500,
                    {
                        "error": str(exc),
                        "walletAddress": wallet_address,
                    },
                )
            return

        if parsed.path == "/api/delete-snapshot":
            config = load_config()
            query = parse_qs(parsed.query)
            wallet_address = query.get("wallet", [config.get("userAddress", DEFAULT_USER)])[0]
            snapshot_id_raw = query.get("snapshot_id", [""])[0]
            debug_log(
                "api_delete_snapshot_request",
                wallet=wallet_address,
                snapshot_id=snapshot_id_raw,
                path=self.path,
            )
            try:
                snapshot_id = int(snapshot_id_raw)
                payload = delete_snapshot_for_wallet(wallet_address, snapshot_id)
                debug_log(
                    "api_delete_snapshot_success",
                    wallet=wallet_address,
                    snapshot_id=snapshot_id,
                )
                self._send_json(200, payload)
            except Exception as exc:
                debug_log(
                    "api_delete_snapshot_error",
                    wallet=wallet_address,
                    snapshot_id=snapshot_id_raw,
                    error=str(exc),
                )
                self._send_json(
                    500,
                    {
                        "error": str(exc),
                        "walletAddress": wallet_address,
                        "snapshotId": snapshot_id_raw,
                    },
                )
            return

        self.send_response(404)
        self.end_headers()


def main() -> None:
    host = os.getenv("DASHBOARD_HOST", HOST)
    port = int(os.getenv("DASHBOARD_PORT", str(PORT)))
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Dashboard running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

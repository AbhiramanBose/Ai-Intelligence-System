#!/usr/bin/env python3

import argparse
import time
from typing import Any

import requests
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout


console = Console()


def fetch_json(url: str) -> dict[str, Any]:
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"error": str(exc)}


def build_metrics_table(metrics: dict[str, Any]) -> Table:
    table = Table(title="Live Store Metrics", expand=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    if "error" in metrics:
        table.add_row("error", metrics["error"])
        return table

    table.add_row("store_id", str(metrics.get("store_id")))
    table.add_row("unique_visitors", str(metrics.get("unique_visitors", 0)))
    table.add_row("conversion_rate", str(metrics.get("conversion_rate", 0.0)))
    table.add_row("current_queue_depth", str(metrics.get("current_queue_depth", 0)))
    table.add_row("abandonment_rate", str(metrics.get("abandonment_rate", 0.0)))

    avg_dwell = metrics.get("avg_dwell_per_zone", {}) or {}
    if avg_dwell:
        table.add_section()
        for zone, dwell in avg_dwell.items():
            table.add_row(f"avg_dwell::{zone}", f"{dwell} ms")

    return table


def build_funnel_table(funnel_response: dict[str, Any]) -> Table:
    table = Table(title="Live Funnel", expand=True)
    table.add_column("Stage", style="bold")
    table.add_column("Count")
    table.add_column("Drop-off %")

    if "error" in funnel_response:
        table.add_row("error", funnel_response["error"], "-")
        return table

    for item in funnel_response.get("funnel", []):
        table.add_row(
            str(item.get("stage")),
            str(item.get("count")),
            str(item.get("dropoff_percent")),
        )

    return table


def build_heatmap_table(heatmap_response: dict[str, Any]) -> Table:
    table = Table(title="Zone Heatmap", expand=True)
    table.add_column("Zone", style="bold")
    table.add_column("Visits")
    table.add_column("Avg Dwell")
    table.add_column("Heat")
    table.add_column("Confidence")

    if "error" in heatmap_response:
        table.add_row("error", "-", "-", "-", heatmap_response["error"])
        return table

    zones = sorted(
        heatmap_response.get("zones", []),
        key=lambda item: item.get("heat_score", 0),
        reverse=True,
    )

    for zone in zones[:8]:
        table.add_row(
            str(zone.get("zone_id")),
            str(zone.get("visit_count")),
            str(zone.get("avg_dwell_ms")),
            str(zone.get("heat_score")),
            str(zone.get("data_confidence")),
        )

    return table


def build_anomaly_table(anomaly_response: dict[str, Any]) -> Table:
    table = Table(title="Active Anomalies", expand=True)
    table.add_column("Type", style="bold")
    table.add_column("Severity")
    table.add_column("Suggested Action")

    if "error" in anomaly_response:
        table.add_row("error", "-", anomaly_response["error"])
        return table

    anomalies = anomaly_response.get("anomalies", [])

    if not anomalies:
        table.add_row("NONE", "-", "No active anomaly.")
        return table

    for anomaly in anomalies:
        table.add_row(
            str(anomaly.get("type")),
            str(anomaly.get("severity")),
            str(anomaly.get("suggested_action")),
        )

    return table


def build_health_panel(health: dict[str, Any]) -> Panel:
    if "error" in health:
        content = f"API error: {health['error']}"
        return Panel(content, title="Health", border_style="red")

    warnings = health.get("warnings", []) or []
    warning_text = "\n".join(
        f"- {warning.get('type')}: {warning.get('message')}"
        for warning in warnings
    ) or "No warnings"

    content = (
        f"status: {health.get('status')}\n"
        f"database: {health.get('database')}\n"
        f"warnings:\n{warning_text}"
    )

    return Panel(content, title="Health")


def build_dashboard(base_url: str, store_id: str) -> Layout:
    metrics = fetch_json(f"{base_url}/stores/{store_id}/metrics")
    funnel = fetch_json(f"{base_url}/stores/{store_id}/funnel")
    heatmap = fetch_json(f"{base_url}/stores/{store_id}/heatmap")
    anomalies = fetch_json(f"{base_url}/stores/{store_id}/anomalies")
    health = fetch_json(f"{base_url}/health")

    layout = Layout()

    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )

    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    layout["left"].split_column(
        Layout(build_metrics_table(metrics)),
        Layout(build_funnel_table(funnel)),
    )

    layout["right"].split_column(
        Layout(build_heatmap_table(heatmap)),
        Layout(build_anomaly_table(anomalies)),
    )

    layout["header"].update(
        Panel(
            f"Store Intelligence Live Dashboard | store_id={store_id} | API={base_url}",
            title="Purplle Tech Challenge 2026",
        )
    )

    layout["footer"].update(build_health_panel(health))

    return layout


def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal live dashboard for Store Intelligence API.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--store-id", default="ST1008")
    parser.add_argument("--refresh-seconds", type=float, default=2.0)
    args = parser.parse_args()

    console.print("[bold green]Starting terminal dashboard. Press CTRL+C to stop.[/bold green]")

    with Live(
        build_dashboard(args.base_url, args.store_id),
        refresh_per_second=1,
        screen=True,
    ) as live:
        while True:
            time.sleep(args.refresh_seconds)
            live.update(build_dashboard(args.base_url, args.store_id))


if __name__ == "__main__":
    main()

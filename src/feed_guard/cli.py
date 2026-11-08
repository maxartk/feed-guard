"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import build_state, check_feed, parse_feed, render_report


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"Varování: {path} není platný JSON, beru prázdný stav.", file=sys.stderr)
        return {}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="feed-guard", description="Kontrola dodavatelského feedu")
    parser.add_argument("check", nargs="?", default="check")
    parser.add_argument("--feed", required=True, help="CSV feed dodavatele")
    parser.add_argument("--state", default="state.json", help="Snapshot předchozího běhu")
    parser.add_argument("--report", default="report.md", help="Markdown report")
    parser.add_argument("--json", dest="json_out", default="alerts.json", help="Nálezy jako JSON")
    parser.add_argument("--low-stock", type=int, default=5, help="Limit nízkého skladu")
    parser.add_argument("--price-change", type=float, default=10.0, help="Limit změny ceny v %%")
    parser.add_argument("--dry-run", action="store_true", help="Nepřepisovat state")
    args = parser.parse_args(argv)

    feed_path = Path(args.feed)
    if not feed_path.exists():
        print(f"Feed nenalezen: {feed_path}", file=sys.stderr)
        return 1

    products = parse_feed(feed_path.read_text(encoding="utf-8-sig"))
    state_path = Path(args.state)
    previous = load_state(state_path)

    alerts = check_feed(products, previous, args.low_stock, args.price_change)
    meta = {"feed": feed_path.name, "low_stock": args.low_stock, "price_change_pct": args.price_change}

    Path(args.report).write_text(render_report(alerts, products, meta), encoding="utf-8")
    Path(args.json_out).write_text(
        json.dumps({"summary": meta, "alerts": [a.as_dict() for a in alerts]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not args.dry_run:
        state_path.write_text(json.dumps(build_state(products), ensure_ascii=False, indent=2), encoding="utf-8")

    for alert in alerts:
        print(f"[{alert.severity:7}] {alert.sku:14} {alert.message}")

    return 2 if alerts else 0


if __name__ == "__main__":
    raise SystemExit(main())

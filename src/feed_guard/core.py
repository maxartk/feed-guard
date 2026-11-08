"""Core checks for supplier feeds. Pure functions, no I/O."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

STATUS_ACTIVE = "active"


@dataclass
class Product:
    sku: str
    name: str = ""
    price: float = 0.0
    stock: int = 0
    status: str = STATUS_ACTIVE
    currency: str = "CZK"
    raw_price: str = ""

    @property
    def is_active(self) -> bool:
        return self.status.strip().lower() == STATUS_ACTIVE


@dataclass
class Alert:
    kind: str
    sku: str
    message: str
    severity: str = "warning"
    data: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "sku": self.sku,
            "message": self.message,
            "severity": self.severity,
            "data": self.data,
        }


def _to_float(value: str) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value: str) -> int:
    number = _to_float(value)
    return int(number) if number is not None else 0


def parse_feed(text: str) -> List[Product]:
    """Parse CSV feed text into products, preserving duplicates."""
    reader = csv.DictReader(io.StringIO(text))
    products: List[Product] = []
    for row in reader:
        sku = (row.get("sku") or "").strip()
        if not sku:
            continue
        products.append(
            Product(
                sku=sku,
                name=(row.get("name") or "").strip(),
                price=_to_float(row.get("price")) or 0.0,
                stock=_to_int(row.get("stock")),
                status=(row.get("status") or STATUS_ACTIVE).strip(),
                currency=(row.get("currency") or "CZK").strip(),
                raw_price=(row.get("price") or "").strip(),
            )
        )
    return products


def index_by_sku(products: Iterable[Product]) -> Dict[str, Product]:
    indexed: Dict[str, Product] = {}
    for product in products:
        indexed.setdefault(product.sku, product)
    return indexed


def check_feed(
    products: List[Product],
    previous: Optional[Dict[str, Dict[str, Any]]] = None,
    low_stock: int = 5,
    price_change_pct: float = 10.0,
) -> List[Alert]:
    """Run all checks and return alerts sorted by severity then SKU."""
    previous = previous or {}
    alerts: List[Alert] = []

    seen: Dict[str, int] = {}
    for product in products:
        seen[product.sku] = seen.get(product.sku, 0) + 1
    for sku, count in sorted(seen.items()):
        if count > 1:
            alerts.append(
                Alert(
                    kind="duplicate_sku",
                    sku=sku,
                    message=f"SKU je ve feedu {count}x",
                    severity="error",
                    data={"count": count},
                )
            )

    for product in products:
        if product.price <= 0:
            alerts.append(
                Alert(
                    kind="negative_price",
                    sku=product.sku,
                    message=f"Neplatná cena: '{product.raw_price}'",
                    severity="error",
                    data={"price": product.raw_price},
                )
            )

        if product.is_active and product.stock <= 0:
            alerts.append(
                Alert(
                    kind="out_of_stock_listed",
                    sku=product.sku,
                    message="Produkt je aktivní, ale sklad je 0",
                    severity="error",
                    data={"stock": product.stock, "name": product.name},
                )
            )
        elif 0 < product.stock <= low_stock:
            alerts.append(
                Alert(
                    kind="low_stock",
                    sku=product.sku,
                    message=f"Nízký sklad: {product.stock} ks",
                    severity="warning",
                    data={"stock": product.stock, "name": product.name},
                )
            )

    current_index = index_by_sku(products)
    for sku, previous_row in previous.items():
        if sku not in current_index:
            alerts.append(
                Alert(
                    kind="removed_sku",
                    sku=sku,
                    message="SKU zmizelo z feedu dodavatele",
                    severity="warning",
                    data={"previous_name": previous_row.get("name", "")},
                )
            )

    for sku, product in current_index.items():
        if sku not in previous:
            alerts.append(
                Alert(
                    kind="new_sku",
                    sku=sku,
                    message="Nové SKU ve feedu",
                    severity="info",
                    data={"name": product.name, "price": product.price},
                )
            )
            continue

        old_price = _to_float(previous[sku].get("price"))
        if old_price and old_price > 0:
            change = (product.price - old_price) / old_price * 100.0
            if abs(change) >= price_change_pct:
                direction = "zdražení" if change > 0 else "zlevnění"
                alerts.append(
                    Alert(
                        kind="price_change",
                        sku=sku,
                        message=f"{direction.capitalize()} o {change:+.1f} %",
                        severity="warning" if change > 0 else "info",
                        data={
                            "old_price": old_price,
                            "new_price": product.price,
                            "change_pct": round(change, 2),
                        },
                    )
                )

    order = {"error": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: (order.get(a.severity, 3), a.kind, a.sku))
    return alerts


def build_state(products: List[Product]) -> Dict[str, Dict[str, Any]]:
    """Snapshot for the next run."""
    return {
        sku: {"price": p.price, "stock": p.stock, "name": p.name, "status": p.status}
        for sku, p in index_by_sku(products).items()
    }


def render_report(alerts: List[Alert], products: List[Product], meta: Dict[str, Any]) -> str:
    errors = [a for a in alerts if a.severity == "error"]
    warnings = [a for a in alerts if a.severity == "warning"]
    infos = [a for a in alerts if a.severity == "info"]
    lines = [
        "# Kontrola feedu",
        "",
        f"- Produktů ve feedu: **{len(index_by_sku(products))}**",
        f"- Chyby: **{len(errors)}**, varování: **{len(warnings)}**, info: **{len(infos)}**",
    ]
    for key, label in (("feed", "Feed"), ("low_stock", "Limit skladu"), ("price_change_pct", "Limit změny ceny")):
        if key in meta:
            lines.append(f"- {label}: `{meta[key]}`")
    lines.append("")

    if not alerts:
        lines += ["Feed je v pořádku. ✅", ""]
        return "\n".join(lines)

    for title, group in (("Chyby", errors), ("Varování", warnings), ("Info", infos)):
        if not group:
            continue
        lines += [f"## {title} ({len(group)})", ""]
        for alert in group:
            lines.append(f"- **{alert.sku}** — {alert.message} _({alert.kind})_")
        lines.append("")

    return "\n".join(lines)

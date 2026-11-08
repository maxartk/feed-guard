# feed-guard

Kontrola dodavatelského produktového feedu před importem do e-shopu. Najde to, co
ruční kontrola přes Excel přehlédne: zdražení, výpadky skladu, duplicitní SKU,
položky „skladem 0" nabízené jako dostupné a nově zmizelé produkty.

Bez závislostí (jen standardní knihovna Pythonu), bez API klíčů, bez cloudu.

## Proč

Ve vláknech o e-commerce automatizaci se opakuje stejná zkušenost: nejvíc času a
peněz neušetří „AI chatbot", ale hlídání feedu a skladu — oversell, neaktuální
ceny, položky, které dodavatel zrušil a e-shop je pořád prodává.

## Použití

```bash
python -m feed_guard check \
  --feed examples/supplier_feed.csv \
  --state examples/state.json \
  --report report.md \
  --json alerts.json \
  --low-stock 5 \
  --price-change 10
```

`state.json` se po kontrole přepíše aktuálním stavem, takže další běh porovnává
proti předchozímu snapshotu.

Exit kód: `0` = bez nálezů, `2` = jsou nálezy (vhodné pro cron/CI gate).

## Co kontroluje

| Kontrola | Význam |
|---|---|
| `new_sku` / `removed_sku` | produkt se objevil / zmizel z feedu |
| `price_change` | změna ceny nad `--price-change` % |
| `low_stock` | sklad pod `--low-stock` (výchozí 5) |
| `out_of_stock_listed` | `stock = 0`, ale produkt je `active` |
| `duplicate_sku` | stejné SKU vícekrát v jednom feedu |
| `negative_price` | cena ≤ 0 nebo nečíselná |

## Formát feedu

CSV s hlavičkou `sku,name,price,stock,status,currency` (`status` = `active` / `hidden`).

## Výstup

- `report.md` — lidsky čitelný přehled pro sklad/obchod
- `alerts.json` — strojově čitelný seznam pro napojení (n8n, Make, e-mail, Telegram)

## Integrace

Skript je záměrně „hloupý" a deterministický — hodí se jako krok před importem nebo
jako cron úloha, která pošle `alerts.json` dál. Nemění ceny ani dostupnost sám;
jen reportuje, rozhodnutí zůstává na člověku.

## Testy

```bash
python -m unittest discover -s tests -v
```

MIT licencováno.

## Poznámka ke vzniku

Téma vychází z opakované zkušenosti obchodníků v diskusích o automatizaci e-shopů
(oversell, neaktuální ceny ve feedu, zboží, které dodavatel zrušil). Kód je vlastní
implementace, bez převzatých částí.

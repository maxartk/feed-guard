import unittest

from feed_guard.core import build_state, check_feed, parse_feed, render_report

FEED = """sku,name,price,stock,status,currency
A-1,Rolety Den,1290.00,12,active,CZK
A-2,Žaluzie Mini,890,3,active,CZK
A-3,Plisse,0,0,active,CZK
A-1,Rolety Den duplikát,1290,12,active,CZK
"""


class ParseTests(unittest.TestCase):
    def test_parses_products_and_keeps_duplicates(self):
        products = parse_feed(FEED)
        self.assertEqual(len(products), 4)
        self.assertEqual(products[0].sku, "A-1")
        self.assertEqual(products[0].price, 1290.0)

    def test_comma_decimal_and_spaces(self):
        products = parse_feed("sku,name,price,stock\nB-1,Test,\"1 290,50\",1\n")
        self.assertAlmostEqual(products[0].price, 1290.50)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.products = parse_feed(FEED)

    def test_detects_duplicate(self):
        alerts = check_feed(self.products)
        kinds = [a.kind for a in alerts]
        self.assertIn("duplicate_sku", kinds)

    def test_detects_zero_price_active_item(self):
        alerts = check_feed(self.products)
        self.assertTrue(any(a.kind == "negative_price" and a.sku == "A-3" for a in alerts))
        self.assertTrue(any(a.kind == "out_of_stock_listed" and a.sku == "A-3" for a in alerts))

    def test_low_stock_threshold(self):
        alerts = check_feed(self.products, low_stock=5)
        self.assertTrue(any(a.kind == "low_stock" and a.sku == "A-2" for a in alerts))
        self.assertFalse(any(a.kind == "low_stock" and a.sku == "A-1" for a in alerts))

    def test_price_change_against_previous_state(self):
        previous = {"A-1": {"price": 1000.0, "stock": 12, "name": "Rolety Den"}}
        alerts = check_feed(self.products, previous, price_change_pct=10)
        price_alerts = [a for a in alerts if a.kind == "price_change"]
        self.assertEqual(len(price_alerts), 1)
        self.assertAlmostEqual(price_alerts[0].data["change_pct"], 29.0)

    def test_removed_and_new_sku(self):
        previous = {"OLD-9": {"price": 10, "stock": 1, "name": "Starý"}}
        alerts = check_feed(self.products, previous)
        kinds = {a.kind for a in alerts}
        self.assertIn("removed_sku", kinds)
        self.assertIn("new_sku", kinds)

    def test_errors_sort_first(self):
        alerts = check_feed(self.products)
        self.assertEqual(alerts[0].severity, "error")

    def test_state_roundtrip(self):
        state = build_state(self.products)
        self.assertIn("A-1", state)
        self.assertEqual(state["A-2"]["stock"], 3)

    def test_report_contains_counts(self):
        alerts = check_feed(self.products)
        report = render_report(alerts, self.products, {"low_stock": 5})
        self.assertIn("Chyby", report)
        self.assertIn("A-3", report)


if __name__ == "__main__":
    unittest.main()

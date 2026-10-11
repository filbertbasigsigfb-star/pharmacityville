"""Regression tests for delivery contact validation (no Flask runtime required)."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_validator():
    tree = ast.parse((ROOT / 'customer_orders.py').read_text(encoding='utf8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'validate_delivery_details')
    namespace = {'re': re}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<validator>', 'exec'), namespace)
    return namespace['validate_delivery_details']


class DeliveryContactValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validate = staticmethod(load_validator())

    def test_accepts_standard_philippine_mobile(self):
        data = self.validate({'delivery_name': 'Jane Customer', 'delivery_phone': '09123456789', 'delivery_address': '11 Main Street, Barangay A, Taytay, Rizal'})
        self.assertEqual(data['delivery_phone'], '09123456789')
        self.assertEqual(data['delivery_name'], 'Jane Customer')

    def test_accepts_international_format_and_normalizes_spacing(self):
        data = self.validate({'delivery_name': '  Jane Customer  ', 'delivery_phone': '+63 912-345-6789', 'delivery_address': '  11 Main Street, Taytay, Rizal  '})
        self.assertEqual(data['delivery_phone'], '+639123456789')
        self.assertEqual(data['delivery_address'], '11 Main Street, Taytay, Rizal')

    def test_rejects_missing_or_invalid_values(self):
        valid={'delivery_name': 'Jane Customer', 'delivery_phone': '09123456789', 'delivery_address': '11 Main Street, Taytay, Rizal'}
        for key, value in [('delivery_name', 'X'), ('delivery_name', ''), ('delivery_phone', '09123'), ('delivery_phone', '12345678901'), ('delivery_address', 'Short'), ('delivery_address', '')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.validate({**valid, key: value})

    def test_online_checkout_requires_validation_before_xendit(self):
        source=(ROOT / 'payments.py').read_text()
        self.assertLess(source.index('delivery_data = validate_delivery_details(request.form)'),source.index('pdata = create_provider_session('))
        self.assertIn('payment_data=pdata, delivery_data=delivery_data', source)

    def test_delivery_fields_display_for_paid_orders(self):
        for filename in ['templates/order_detail.html', 'templates/admin_order_detail.html']:
            text=(ROOT / filename).read_text()
            self.assertIn("order.payment_method in ['online', 'cod']", text)
            self.assertIn('order.delivery_address',text)
        self.assertIn('id="online_delivery_address"',(ROOT / 'templates/checkout.html').read_text())

if __name__=='__main__':
    unittest.main()
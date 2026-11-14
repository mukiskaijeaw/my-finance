import unittest
from datetime import date
from comparison_states import comparison_states
from simulator import demo_profile


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 11, 12)
        self.profile = demo_profile(self.day)

    def test_dynamic_prices(self):
        rows = comparison_states(self.profile, '3200', '1500', self.day)
        self.assertEqual([r['price'] for r in rows], ['2560.00', '3200.00', '3840.00'])
        self.assertEqual([r['remainingMoney'] for r in rows], ['3940.00', '3300.00', '2660.00'])
        self.assertTrue(all(r['demoFinancialStatus'] == 'AFFORDABLE' for r in rows))

    def test_three_actual_statuses(self):
        rows = comparison_states(self.profile, '5500', '1500', self.day)
        self.assertEqual([r['demoFinancialStatus'] for r in rows],
                         ['AFFORDABLE', 'BUY_WITH_CAUTION', 'WAIT_AND_SAVE'])

    def test_unknown_not_zero(self):
        self.profile.pop('cash')
        rows = comparison_states(self.profile, '1560', '1500', self.day)
        self.assertTrue(all(r['demoFinancialStatus'] == 'INSUFFICIENT_DATA' for r in rows))
        self.assertTrue(all(r['remainingMoney'] is None for r in rows))

    def test_invalid_price(self):
        for price in ['NaN', '-1', 'Infinity']:
            with self.assertRaises(ValueError):
                comparison_states(self.profile, price, '1500', self.day)


if __name__ == '__main__':
    unittest.main()

import unittest

from deploy import Plan, Step


class TestPlan(unittest.TestCase):

    def test_create(self):
        f = object()
        u = ''
        p = Plan(f, u)
        self.assertEqual(p.__str__(), 'Plan 0')

if __name__ == '__main__':
    unittest.main()
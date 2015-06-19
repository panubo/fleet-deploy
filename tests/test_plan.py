import unittest

from deploy import Plan, Step


class TestPlan(unittest.TestCase):

    def test_create(self):
        f = object()
        s = list()
        u = ''
        p = Plan(f, s, u)
        self.assertEqual(p.__str__(), 'Plan 0')

if __name__ == '__main__':
    unittest.main()
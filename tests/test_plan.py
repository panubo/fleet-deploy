import unittest

from deploy import Plan, Step


class TestPlan(unittest.TestCase):

    def setUp(self):
        fleet_client = object()
        unit_template = ''
        self.plan = Plan(fleet_client, unit_template)

    def test_str(self):
        self.assertEqual(self.plan.__str__(), 'Plan 0')

    def test_add_steps(self):
        self.plan.steps.append(Step('foo', 'destroy'))
        self.plan.steps.append(Step('bar', 'spawn'))
        self.assertEqual(len(self.plan.steps), 2)

    def test_execute_external_script(self):
        self.plan.steps.append(Step('./tests/atomic.sh', 'external_script'))
        self.plan.execute(0)

if __name__ == '__main__':
    unittest.main()
import unittest

from deploy import Plan, Step


class TestPlan(unittest.TestCase):

    def setUp(self):
        fleet_client = object()
        service_name = 'test-service'
        full_service_name = service_name + '-abc123'
        unit_template = ''
        self.plan = Plan(fleet_client, service_name, full_service_name, unit_template)

    def test_str(self):
        self.assertEqual(self.plan.__str__(), '<Plan Object (0 steps)>')

    def test_add_steps(self):
        self.plan.steps.append(Step('foo', 'destroy'))
        self.plan.steps.append(Step('bar', 'spawn'))
        self.assertEqual(len(self.plan.steps), 2)

    def test_execute_external_script(self):
        self.plan.steps.append(Step('foo', 'spawn'))
        self.plan.steps.append(Step('bar', 'destroy'))
        self.plan.steps.append(Step('./tests/atomic.sh', 'external_script'))
        self.plan.execute(2)

if __name__ == '__main__':
    unittest.main()

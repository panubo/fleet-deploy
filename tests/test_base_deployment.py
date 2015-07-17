import unittest

from deploy import BaseDeployment


class FakeUnit(object):

    def __init__(self, name, currentState, systemdSubState):
        self.name = name
        self.currentState = currentState
        self.systemdSubState = systemdSubState

    def __hash__(self):
        return hash((self.name))


class FakeFleetClient(object):

    test_data = [
        {'name': 'foo@.service', 'currentState': 'inactive', 'systemdSubState': 'inactive'},
        {'name': 'foo-abc123@1.service', 'currentState': 'launched', 'systemdSubState': 'running'},
        {'name': 'foo-abc123@2.service', 'currentState': 'launched', 'systemdSubState': 'running'},
    ]

    def list_units(self):
        return self.test_data

    def get_unit(self, unit_name):
        return "Unit file of %s" % unit_name

    def set_unit_desired_state(self, unit, state):
        print("Fleet set: %s -> %s" % (unit, state))

    def list_unit_states(self):
        states = list()
        for u in self.test_data:
            states.append(FakeUnit(u['name'], u['currentState'], u['systemdSubState']))
        return states


class TestBaseDeployment(unittest.TestCase):

    def setUp(self):

        fleet_client = FakeFleetClient()
        service_name = 'foo'
        tag = 'mytag'

        self.deployment = BaseDeployment(fleet_client, service_name, tag)
        self.assertEqual(self.deployment.fleet, fleet_client)
        self.assertEqual(self.deployment.service_name, service_name)
        self.assertEqual(self.deployment.tag, tag)

    def test_deployment(self):

        plan_output = ['*** Base Deployment Deployment Plan ***',
                       '==> Details',
                       'Unit: foo-abc123@1.service (launched).',
                       'Unit: foo-abc123@2.service (launched).',
                       'Chunking: 1 units',
                       '==> Deployment Plan',
                       '==> Stage 1',
                       'Step 1: stop foo-abc123@1.service',
                       'Step 2: start foo-abc123@1.service',
                       '==> Stage 2',
                       'Step 3: stop foo-abc123@2.service',
                       'Step 4: start foo-abc123@2.service']


        self.assertEqual(self.deployment.__str__(), '<Base Deployment Object: (0 plans) (0 units)>')
        self.deployment.load(2)  # add two
        self.deployment.update_chunking(chunking=1, chunking_percent=None)
        self.deployment.create_plans()

        # Check output is what we expected
        self.assertEqual(self.deployment.describe_plans(), plan_output)

        # Todo we can't actually test the running, ... yet
        #self.deployment.run_plans()

if __name__ == '__main__':
    unittest.main()
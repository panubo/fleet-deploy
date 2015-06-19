import unittest

from deploy import BaseDeployment


class TestBaseDeployment(unittest.TestCase):

    def test_create(self):

        fleet_client = object()
        service_name = 'foo'
        tag = 'mytag'

        d = BaseDeployment(fleet_client, service_name, tag)
        self.assertEqual(d.fleet, fleet_client)
        self.assertEqual(d.service_name, service_name)
        self.assertEqual(d.tag, tag)

if __name__ == '__main__':
    unittest.main()
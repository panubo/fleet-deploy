import unittest

from deploy import FleetConnection, FLEET_ENDPOINT_DEFAULT


class TestFleetConnection(unittest.TestCase):

    def test_failed_connection_handling(self):
        with self.assertRaises(SystemExit):
            c = FleetConnection(fleet_uri=FLEET_ENDPOINT_DEFAULT)

if __name__ == '__main__':
    unittest.main()
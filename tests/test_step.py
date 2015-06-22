import unittest

from deploy import Step


class TestStep(unittest.TestCase):

    def setUp(self):
        self.step = Step('foo', 'stop')

    def test_create(self):
        self.assertEqual(self.step.__str__(), 'stop foo')
        self.assertEqual(self.step.name, 'foo')
        self.assertEqual(self.step.action, 'stop')

    def test_invalid_action(self):
        with self.assertRaises(Exception):
            s = Step('foo', 'xxx')

    def test_valid_action(self):
        for action in ('start', 'stop', 'spawn', 'destroy', 'external_script'):
            s = Step('foo', action)

if __name__ == '__main__':
    unittest.main()
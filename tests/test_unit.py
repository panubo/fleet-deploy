import unittest

from deploy import Unit


class TestUnit(unittest.TestCase):

    def test_create(self):
        i = Unit('foo', 'inactive', 'spawn')

        self.assertEqual(i.__str__(), 'foo')
        self.assertEqual(i.name, 'foo')
        self.assertEqual(i.state, 'inactive')
        self.assertEqual(i.required_action, 'spawn')
        self.assertEqual(i.details, 'foo inactive')

    def test_invalid_state(self):
        with self.assertRaises(Exception):
            i = Unit('foo', 'xxxx', 'spawn')

    def test_invalid_action(self):
        with self.assertRaises(Exception):
            i = Unit('foo', 'inactive', 'xxx')

if __name__ == '__main__':
    unittest.main()
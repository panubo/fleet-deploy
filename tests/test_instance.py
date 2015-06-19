import unittest

from deploy import Instance


class TestInstance(unittest.TestCase):

    def test_create(self):
        i = Instance('foo', 'inactive', 'spawn')

        self.assertEqual(i.__str__(), 'foo')
        self.assertEqual(i.name, 'foo')
        self.assertEqual(i.state, 'inactive')
        self.assertEqual(i.required_action, 'spawn')
        self.assertEqual(i.details, 'foo inactive')

    def test_invalid_state(self):
        with self.assertRaises(Exception):
            i = Instance('foo', 'xxxx', 'spawn')

    def test_invalid_action(self):
        with self.assertRaises(Exception):
            i = Instance('foo', 'inactive', 'xxx')

if __name__ == '__main__':
    unittest.main()
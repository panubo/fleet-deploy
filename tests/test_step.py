import unittest

from deploy import Step


class TestStep(unittest.TestCase):

    def test_create(self):
        s = Step('foo', 'stop')
        self.assertEqual(s.__str__(), 'stop foo')
        self.assertEqual(s.name, 'foo')
        self.assertEqual(s.action, 'stop')

    def test_invalid_action(self):
        with self.assertRaises(Exception):
            s = Step('foo', 'xxx')

if __name__ == '__main__':
    unittest.main()
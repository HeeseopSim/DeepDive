import unittest
from waiting_queue import WaitingQueue


class T(unittest.TestCase):
    def test_complete_removes_top(self):
        q = WaitingQueue()
        q.add("가", 2); q.add("나", 3); q.add("다", 1)
        self.assertEqual(q.complete()["name"], "가")
        self.assertEqual(q.items[0]["name"], "나")
        s = q.status(3)
        self.assertEqual((s["position"], s["teamsAhead"], s["peopleAhead"]), (2, 1, 3))

    def test_validation(self):
        q = WaitingQueue()
        for bad in [("", 1), ("a", 0), ("a", "x"), ("a", 100)]:
            with self.assertRaises(ValueError):
                q.add(*bad)
        self.assertIsNone(WaitingQueue().complete())


if __name__ == "__main__":
    unittest.main()

import os
from unittest import TestCase
from servequnit.factory import ServerFactory
from servequnit.tester import QunitSeleniumTester, TestFailedError

class QunitSeleniumTesterTestCase(TestCase):
    def _make_tester(self, server, suffix=None):
        suffix = suffix or "oneshot/"
        url = server.url + suffix
        hub = "http://127.0.0.1:4444/wd/hub"
        tester = QunitSeleniumTester(url=url, hub=hub)
        return tester

    def test_passing_test_passes(self):
        passing = os.path.join(os.path.dirname(__file__), "data", "passes.js")
        factory = ServerFactory()
        factory.bind_script("test", passing)
        with factory.run() as server:
            tester = self._make_tester(server)
            tester.run()

    def test_failing_test_reports_failure(self):
        passing = os.path.join(os.path.dirname(__file__), "data", "fails.js")
        factory = ServerFactory()
        factory.bind_script("test", passing)
        with factory.run() as server:
            tester = self._make_tester(server)
            self.assertRaises(TestFailedError, tester.run)
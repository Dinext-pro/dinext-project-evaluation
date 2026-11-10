"""Run report regressions and the real Desk scenario on the disposable CI bench."""

import json
import os
from pathlib import Path
import signal
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen
import xml.etree.ElementTree as ET


bench = Path(os.environ["RUNNER_TEMP"]) / "dinext-test-bench"
artifacts = Path(os.environ["RUNNER_TEMP"]) / "scoring-acceptance"
artifacts.mkdir()
app = bench / "apps/dinext_project_evaluation"
env = os.environ.copy()
env.update({
	"DEV_SERVER": "1",
	"FRAPPE_SITE": "ci.test",
	"CYPRESS_reporter": "junit",
	"CYPRESS_reporterOptions": json.dumps({"mochaFile": str(artifacts / "browser-[hash].xml")}),
})


def run(*args, cwd=bench, **kwargs):
	subprocess.run([str(arg) for arg in args], cwd=cwd, env=env, check=True, timeout=1200, **kwargs)


# The root-level regression suite needs a real Frappe site context.
root_suite = """
import os, sys, unittest
import frappe, xmlrunner
frappe.init(site='ci.test')
frappe.connect()
frappe.set_user('Administrator')
frappe.flags.in_test = True
try:
    suite = unittest.defaultTestLoader.discover(sys.argv[1], pattern='test_*.py')
    with open(sys.argv[2], 'wb') as output:
        result = xmlrunner.XMLTestRunner(output=output).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
finally:
    frappe.db.rollback()
    frappe.destroy()
"""
run(bench / "env/bin/python", "-c", root_suite, app / "tests", artifacts / "report-unit.xml", cwd=bench / "sites")
run("node", "--test", "--test-reporter=junit", f"--test-reporter-destination={artifacts / 'javascript.xml'}",
	*sorted((app / "tests").glob("*.test.js")), cwd=app)
run("bench", "--site", "ci.test", "set-config", "host_name", "http://localhost:8000")

with (artifacts / "web.log").open("w") as log:
	server = subprocess.Popen(
		["bench", "--site", "ci.test", "serve", "--port", "8000", "--noreload"],
		cwd=bench, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
	)
	try:
		for _ in range(60):
			try:
				with urlopen("http://localhost:8000/api/method/ping", timeout=2) as response:
					if response.status == 200:
						break
			except (URLError, TimeoutError):
				time.sleep(1)
		else:
			raise RuntimeError("The disposable Desk server did not start")
		run("bench", "--site", "ci.test", "run-ui-tests", "dinext_project_evaluation", "--headless",
			"--browser", "electron", "--config", f"screenshotsFolder={artifacts / 'screenshots'}")
	finally:
		os.killpg(server.pid, signal.SIGTERM)
		server.wait(timeout=30)
		run("bench", "--site", "ci.test", "execute", "dinext_project_evaluation.tests.ui_test_helpers.cleanup")

reports = list(artifacts.glob("browser-*.xml"))
assert reports, "Cypress did not produce JUnit evidence"
suites = [suite for report in reports for suite in ET.parse(report).iter("testsuite")]
assert sum(int(suite.get("tests", 0)) for suite in suites) == 2, "Both report scenarios must run"
assert not sum(int(suite.get("failures", 0)) + int(suite.get("errors", 0)) + int(suite.get("skipped", 0)) for suite in suites)
metadata = {"app_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=app, text=True).strip()}
(artifacts / "environment.json").write_text(json.dumps(metadata, indent=2) + "\n")

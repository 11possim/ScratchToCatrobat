import os
import shutil
import tempfile
import unittest

from scratchtobat import common
from scratchtobat import common_testing
from scratchtobat import sb2
from scratchtobat import sb2webapi


class WebApiTest(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.temp_dir = tempfile.mkdtemp()

    def test_can_download_complete_project_from_project_url(self):
        for project_url in common_testing.TEST_PROJECT_URL_TO_NAME_MAP:
            sb2webapi.download_project(project_url, self.temp_dir)
            self.assertTrue(sb2.Project(self.temp_dir))

    def test_fail_on_wrong_url(self):
        for wrong_url in ['http://www.tugraz.at', 'http://www.ist.tugraz.at/', 'http://scratch.mit.edu/', 'http://scratch.mit.edu/projects']:
            with self.assertRaises(common.ScratchtobatError):
                sb2webapi.download_project(wrong_url, self.temp_dir)

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        shutil.rmtree(self.temp_dir)
        assert not os.path.exists(self.temp_dir)

if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()

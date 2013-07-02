from scratchtobat import main, common, testing_common
import os
import unittest
import zipfile
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO


class MainTest(testing_common.ScratchtobatTestCase):

    def test_can_provide_catroid_project_for_scratch_link(self):
        for idx, project_url in enumerate(testing_common.TEST_PROJECT_URL_TO_NAME_MAP):
            output_zip_path = os.path.join(testing_common.get_test_resources_path(), "output{}.zip".format(idx))
            return_val = main.scratchtobat_main([project_url, output_zip_path])
            self.assertEqual(0, return_val)
            self.assertCorrectZipFile(output_zip_path, testing_common.TEST_PROJECT_URL_TO_NAME_MAP[project_url])


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()

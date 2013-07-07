import sys
from scratchtobat import sb2webapi, sb2, sb2tocatrobat, common, sb2extractor
import tempfile

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def scratchtobat_main(argv):
    def check_environment_settings():
        if not "java" in sys.platform:
            common.ScratchtobatError("Must be called with Jython interpreter. Aborting.")
        from java.lang import System
        if System.getProperty("python.security.respectJavaAccessibility") == 'true':
            common.ScratchtobatError("Jython registry property 'python.security.respectJavaAccessibility' must be set to 'false'. Aborting.")

    check_environment_settings()

    # TODO: add with upload zip
    scratch_project_file_or_url = argv[0]
    catroid_zip_path = argv[1]
    temp_download_dir = tempfile.mkdtemp()
    try:
        if scratch_project_file_or_url.startswith("http://"):
            sb2webapi.download_project(scratch_project_file_or_url, temp_download_dir)
        else:
            sb2extractor.extract_project(scratch_project_file_or_url, temp_download_dir)
        project = sb2.Project(temp_download_dir)
        sb2tocatrobat.convert_sb2_project_to_catrobat_zip(project, catroid_zip_path)
    except Exception as e:
        common.log.exception(e)
        return EXIT_FAILURE
    return EXIT_SUCCESS

if __name__ == '__main__':
    sys.exit(scratchtobat_main(sys.argv[1:]))

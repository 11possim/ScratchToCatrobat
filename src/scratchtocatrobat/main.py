#  ScratchToCatrobat: A tool for converting Scratch projects into Catrobat programs.
#  Copyright (C) 2013-2015 The Catrobat Team
#  (http://developer.catrobat.org/credits)
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  An additional term exception under section 7 of the GNU Affero
#  General Public License, version 3, is available at
#  http://developer.catrobat.org/license_additional_term
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see http://www.gnu.org/licenses/.

from __future__ import print_function
import logging
import os
import sys
from docopt import docopt
from scratchtocatrobat import logger
from scratchtocatrobat.tools import helpers

logger.setup_logging()
log = logging.getLogger("scratchtocatrobat.main")
__version__ = helpers.application_info("version")

def run_converter(scratch_project_file_or_url, output_dir,
                  extract_resulting_catrobat=False, temp_rm=True,
                  show_version_only=False, show_info_only=False,
                  archive_name=None):
    def check_base_environment():
        if "java" not in sys.platform:
            raise EnvironmentError("Must be called with Jython interpreter.")
        if System.getProperty(helpers.JYTHON_RESPECT_JAVA_ACCESSIBILITY_PROPERTY) != 'false':
            raise EnvironmentError("Jython registry property '%s' must be set to 'false'." % helpers.JYTHON_RESPECT_JAVA_ACCESSIBILITY_PROPERTY)

    def check_converter_environment():
        # TODO: refactor to combined class with explicit environment check method
        tools.svgtopng._checked_batik_jar_path()
        tools.wavconverter._checked_sox_path()

    try:
        from java.io import IOError
        from java.lang import System
    except ImportError:
        log.error("Must be called with Jython interpreter.")
        return helpers.ExitCode.FAILURE

    # nested import to be able to check for Jython interpreter first
    from scratchtocatrobat import catrobat, common, converter, scratch, scratchwebapi, tools

    try:
        check_base_environment()
        check_converter_environment()

        tag_name = helpers.tag_name_of_used_catroid_hierarchy()
        latest_release_data = helpers.latest_catroid_repository_release_data()
        if show_version_only or show_info_only:
            helpers.print_info_or_version_screen(show_version_only, catrobat.CATROBAT_LANGUAGE_VERSION)
            return helpers.ExitCode.SUCCESS
        elif latest_release_data and tag_name != latest_release_data["tag_name"]:
            print("Latest Catroid release: %s (%s)" % (latest_release_data["tag_name"], latest_release_data["published_at"]))
            print("%sA NEW CATROID RELEASE IS AVAILABLE!\nPLEASE UPDATE THE CLASS HIERARCHY OF THE CONVERTER FROM CATROID VERSION %s TO VERSION %s%s" % (helpers.cli_colors.FAIL, tag_name, latest_release_data["tag_name"], helpers.cli_colors.ENDC))

        log.info("calling converter")
        if not os.path.isdir(output_dir):
            raise EnvironmentError("Output folder must be a directory, but is %s" % output_dir)

        progress_bar = helpers.ProgressBar(None, sys.stdout)
        with common.TemporaryDirectory(remove_on_exit=temp_rm) as scratch_project_dir:
            is_local_project = True
            if scratch_project_file_or_url.startswith("https://"):
                is_local_project = False
                log.info("Downloading project from URL: '{}' to temp dir {} ...".format(scratch_project_file_or_url, scratch_project_dir))
                scratchwebapi.download_project(scratch_project_file_or_url, scratch_project_dir, progress_bar)
            elif os.path.isfile(scratch_project_file_or_url):
                log.info("Extracting project from path: '{}' ...".format(scratch_project_file_or_url))
                common.extract(scratch_project_file_or_url, scratch_project_dir)
            else:
                assert os.path.isdir(scratch_project_file_or_url)
                log.info("Loading project from path: '{}' ...".format(scratch_project_file_or_url))
                scratch_project_dir = scratch_project_file_or_url

            if is_local_project and progress_bar != None:
                project = scratch.RawProject.from_project_folder_path(scratch_project_dir)
                progress_bar.num_of_iterations = project.num_of_iterations_of_local_project(progress_bar)

            project = scratch.Project(scratch_project_dir, progress_bar=progress_bar)
            log.info("Converting scratch project '%s' into output folder: %s", project.name, output_dir)
            converted_project = converter.converted(project, progress_bar)
            catrobat_program_path = converted_project.save_as_catrobat_package_to(output_dir, archive_name, progress_bar)
            if extract_resulting_catrobat:
                extraction_path = os.path.join(output_dir, os.path.splitext(os.path.basename(catrobat_program_path))[0])
                common.rm_dir(extraction_path)
                common.makedirs(extraction_path)
                scratch_output_path = os.path.join(extraction_path, "scratch")
                common.copy_dir(scratch_project_dir, scratch_output_path, overwrite=True)
                common.extract(catrobat_program_path, extraction_path)

        assert progress_bar == None or progress_bar.is_full()
    except (common.ScratchtobatError, EnvironmentError, IOError) as e:
        log.error(e)
        return helpers.ExitCode.FAILURE
    except Exception as e:
        log.exception(e)
        return helpers.ExitCode.FAILURE
    return helpers.ExitCode.SUCCESS

def main():
    log = logging.getLogger("scratchtocatrobat.main")
    usage = '''Scratch to Catrobat converter

    Usage:
      'main.py' <project-url-or-package-path> <output-dir> <archive-name> [--extracted] [--no-temp-rm]
      'main.py' <project-url-or-package-path> <output-dir> [--extracted] [--no-temp-rm]
      'main.py' <project-url-or-package-path> [--extracted] [--no-temp-rm]
      'main.py' --version
      'main.py' --info

    Options:
      -h --help         Shows this screen.
      --version         Shows version of this application.
      --info            Shows information and configuration details about this application.
      -e --extracted    Extract resulting Catrobat program in output-dir.
    '''
    arguments = docopt(usage)
    try:
        kwargs = {}
        kwargs['extract_resulting_catrobat'] = arguments["--extracted"]
        kwargs['temp_rm'] = not arguments["--no-temp-rm"]
        kwargs['show_version_only'] = arguments["--version"]
        kwargs['show_info_only'] = arguments["--info"]
        kwargs['archive_name'] = arguments["<archive-name>"]
        output_dir = helpers.config.get("PATHS", "output")
        output_dir = arguments["<output-dir>"] if arguments["<output-dir>"] != None else output_dir
        project_url_or_package_path = ""
        if arguments["<project-url-or-package-path>"]:
            project_url_or_package_path = arguments["<project-url-or-package-path>"].replace("http://", "https://")
            scratch_base_url = helpers.config.get("SCRATCH_API", "project_base_url")
            if project_url_or_package_path.startswith("https://") and not project_url_or_package_path.startswith(scratch_base_url):
                log.error("No valid scratch URL given {0}[ID]".format(scratch_base_url))
                sys.exit(helpers.ExitCode.FAILURE)
        sys.exit(run_converter(project_url_or_package_path, output_dir, **kwargs))
    except Exception as e:
        log.exception(e)
        sys.exit(helpers.ExitCode.FAILURE)

if __name__ == '__main__':
    main()

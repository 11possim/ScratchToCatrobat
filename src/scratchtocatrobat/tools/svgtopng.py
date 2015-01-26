#  ScratchToCatrobat: A tool for converting Scratch projects into Catrobat programs.
#  Copyright (C) 2013-2014 The Catrobat Team
#  (<http://developer.catrobat.org/credits>)
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
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
import logging
import os
import subprocess

from scratchtocatrobat import common

# TODO: replace CLI call with API
_BATIK_ENVIRONMENT_HOME = "BATIK_HOME"
_BATIK_CLI_JAR = "batik-rasterizer.jar"

log = logging.getLogger(__name__)

_batik_jar_path = None


# TODO: refactor to single mediaconverter class together with wavconverter
def _checked_batik_jar_path():
    if _BATIK_ENVIRONMENT_HOME not in os.environ:
        raise EnvironmentError("Environment variable '{}' must be set to batik library location.".format(_BATIK_ENVIRONMENT_HOME))
    batik_jar_path = os.path.join(os.environ[_BATIK_ENVIRONMENT_HOME], _BATIK_CLI_JAR)
    if not os.path.exists(batik_jar_path):
        raise EnvironmentError("Batik jar '{}' must be existing in {}.".format(batik_jar_path, os.path.dirname(batik_jar_path)))
    _batik_jar_path = batik_jar_path
    return _batik_jar_path


def convert(input_svg_path):
    assert isinstance(input_svg_path, (str, unicode))
    assert os.path.splitext(input_svg_path)[1] == ".svg"

    output_png_path = os.path.splitext(input_svg_path)[0] + ".png"
    try:
        subprocess.check_output(['java', '-jar', _checked_batik_jar_path(), input_svg_path, '-scriptSecurityOff'], stderr=subprocess.STDOUT)
        assert os.path.exists(output_png_path)
    except subprocess.CalledProcessError, e:
        assert e.output
        raise common.ScratchtobatError("PNG to SVG conversion call failed:\n%s" % e.output)

    return output_png_path


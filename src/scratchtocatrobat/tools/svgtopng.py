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
import logging
import os
import tempfile
from scratchtocatrobat import common
from scratchtocatrobat.tools import helpers
from java.io import FileOutputStream
from org.apache.batik.transcoder.image import PNGTranscoder
from org.apache.batik.transcoder import TranscoderInput
from org.apache.batik.transcoder import TranscoderOutput
from java.nio.file import Paths

_BATIK_CLI_JAR = "batik-rasterizer.jar"
_log = logging.getLogger(__name__)
_batik_jar_path = None


# TODO: refactor to single mediaconverter class together with wavconverter
def _checked_batik_jar_path():
#     if _BATIK_ENVIRONMENT_HOME not in os.environ:
#         raise EnvironmentError("Environment variable '{}' must be set to batik library location.".format(_BATIK_ENVIRONMENT_HOME))
    batik_home_dir = helpers.config.get("PATHS", "batik_home")
    batik_jar_path = os.path.join(batik_home_dir, _BATIK_CLI_JAR)
    if not os.path.exists(batik_jar_path):
        raise EnvironmentError("Batik jar '{}' must be existing in {}.".format(batik_jar_path, os.path.dirname(batik_jar_path)))
    _batik_jar_path = batik_jar_path
    return _batik_jar_path

def convert(input_svg_path, rotation_x, rotation_y):
    assert isinstance(input_svg_path, (str, unicode))
    assert os.path.splitext(input_svg_path)[1] == ".svg"

    input_file_name = os.path.splitext(input_svg_path)[0]
    output_png_path = "{}_rotX_{}_rotY_{}.png".format(input_file_name, rotation_x, rotation_y)
    _log.info("      converting '%s' to Pocket Code compatible png '%s'", input_svg_path, output_png_path)
    if os.path.exists(output_png_path):
        _log.info("      nothing to do: '%s' already exists", output_png_path)
        return output_png_path # avoid duplicate conversions!

    try:
        # read input SVG document into Transcoder Input (use Java NIO for this purpose)
        svg_URI_input = Paths.get(input_svg_path).toUri().toURL().toString()
        input_svg_image = TranscoderInput(svg_URI_input)

        # define OutputStream to PNG Image and attach to TranscoderOutput
        png_ostream = FileOutputStream(output_png_path)
        output_png_image = TranscoderOutput(png_ostream)

        # Convert and Write output
        _log.info("      converting '%s' to Pocket Code compatible png '%s'", input_svg_path, output_png_path)
        my_converter = PNGTranscoder()
        my_converter.transcode(input_svg_image, output_png_image)

        assert os.path.exists(output_png_path)
        return output_png_path
    except:
        error = common.ScratchtobatError("PNG to SVG conversion call failed for: %s" % input_svg_path)
    finally:
        # free resources
        if png_ostream != None:
            png_ostream.flush()
            png_ostream.close()

    if error != None:
        raise error

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
import imghdr
import os
import shutil
import unittest

from scratchtocatrobat import common_testing
from scratchtocatrobat.tools import svgtopng
from scratchtocatrobat.tools import helpers

class SvgToPngTest(common_testing.BaseTestCase):

    def test_can_convert_file_from_svg_to_png(self):
        regular_svg_path = os.path.join(common_testing.get_test_project_path("dancing_castle"), "1.svg")
        svg_path_with_fileext = os.path.join(self.temp_dir, "test_path_which_includes_extension_.svg.svg", "1.svg")
        os.makedirs(os.path.dirname(svg_path_with_fileext))
        shutil.copy(regular_svg_path, svg_path_with_fileext)
        for input_svg_path in [regular_svg_path, svg_path_with_fileext]:
            assert os.path.exists(input_svg_path)

            output_png_path = svgtopng.convert(input_svg_path)

            assert os.path.exists(output_png_path) 
            assert imghdr.what(output_png_path) == "png"
            
    def test_first_true_cut_of_png(self):
        img_proc_dir = os.path.join(helpers.APP_PATH, "test", "res", "img_proc_png")
        input_png_path = os.path.join(img_proc_dir, "1.png")
        output_png_path = os.path.join(img_proc_dir, "cat_test_result.png")
        expected_image_path = os.path.join(img_proc_dir, "expected_cat.png")
        
        assert os.path.exists(input_png_path)

        final_image = svgtopng._scale_image(input_png_path)
        
        from javax.imageio import ImageIO
        from java.io import File      
        ImageIO.write(final_image, "PNG", File(output_png_path))
        assert os.path.exists(output_png_path)
        assert imghdr.what(output_png_path) == "png"
        
        from javax.swing import ImageIcon
        bufferd_image = svgtopng._create_buffered_image(ImageIcon(output_png_path).getImage())
        width, height = bufferd_image.getWidth(), bufferd_image.getHeight()
        output_image_matrix = [[bufferd_image.getRGB(i, j) for j in xrange(height)] for i in xrange(width)]
        
        bufferd_image = svgtopng._create_buffered_image(ImageIcon(expected_image_path).getImage())
        width, height = bufferd_image.getWidth(), bufferd_image.getHeight()
        expected_image_matrix = [[bufferd_image.getRGB(i, j) for j in xrange(height)] for i in xrange(width)]
        
        for i in xrange(width):
            for j in xrange(height):
                exp_rgb_val = expected_image_matrix[i][j]
                result_rgb_val = output_image_matrix[i][j]
                assert exp_rgb_val == result_rgb_val
                
    def test_second_true_cut_of_png(self):
        img_proc_dir = os.path.join(helpers.APP_PATH, "test", "res", "img_proc_png")
        input_png_path = os.path.join(img_proc_dir, "input_cape.png")
        output_png_path = os.path.join(img_proc_dir, "cape_test_result.png")
        expected_image_path = os.path.join(img_proc_dir, "expected_cape.png")
        
        assert os.path.exists(input_png_path)

        final_image = svgtopng._scale_image(input_png_path)
        
        from javax.imageio import ImageIO
        from java.io import File      
        ImageIO.write(final_image, "PNG", File(output_png_path))
        assert os.path.exists(output_png_path)
        assert imghdr.what(output_png_path) == "png"
        
        from javax.swing import ImageIcon
        bufferd_image = svgtopng._create_buffered_image(ImageIcon(output_png_path).getImage())
        width, height = bufferd_image.getWidth(), bufferd_image.getHeight()
        output_image_matrix = [[bufferd_image.getRGB(i, j) for j in xrange(height)] for i in xrange(width)]
        
        bufferd_image = svgtopng._create_buffered_image(ImageIcon(expected_image_path).getImage())
        width, height = bufferd_image.getWidth(), bufferd_image.getHeight()
        expected_image_matrix = [[bufferd_image.getRGB(i, j) for j in xrange(height)] for i in xrange(width)]
        
        for i in xrange(width):
            for j in xrange(height):
                exp_rgb_val = expected_image_matrix[i][j]
                result_rgb_val = output_image_matrix[i][j]
                assert exp_rgb_val == result_rgb_val
                
    def test_parse_svgfile_and_convert_to_png(self):
        img_proc_dir = os.path.join(helpers.APP_PATH, "test", "res", "img_proc_png")
        input_svg_path = os.path.join(img_proc_dir, "input_antenna.png")
        output_png_path = os.path.join(img_proc_dir, "antenna_test_result.png")
        expected_image_path = os.path.join(img_proc_dir, "expected_antenna.png")
        
        assert os.path.exists(input_svg_path)

        final_image = svgtopng._scale_image(input_png_path)
        
        from javax.imageio import ImageIO
        from java.io import File      
        ImageIO.write(final_image, "PNG", File(output_png_path))
        assert os.path.exists(output_png_path)
        assert imghdr.what(output_png_path) == "png"
        
        from javax.swing import ImageIcon
        bufferd_image = svgtopng._create_buffered_image(ImageIcon(output_png_path).getImage())
        width, height = bufferd_image.getWidth(), bufferd_image.getHeight()
        output_image_matrix = [[bufferd_image.getRGB(i, j) for j in xrange(height)] for i in xrange(width)]
        
        bufferd_image = svgtopng._create_buffered_image(ImageIcon(expected_image_path).getImage())
        width, height = bufferd_image.getWidth(), bufferd_image.getHeight()
        expected_image_matrix = [[bufferd_image.getRGB(i, j) for j in xrange(height)] for i in xrange(width)]
        
        for i in xrange(width):
            for j in xrange(height):
                exp_rgb_val = expected_image_matrix[i][j]
                result_rgb_val = output_image_matrix[i][j]
                assert exp_rgb_val == result_rgb_val
                


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()


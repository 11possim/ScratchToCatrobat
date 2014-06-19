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
import org.catrobat.catroid.common as catcommon

ANDROID_IGNORE_MEDIA_MARKER_FILE_NAME = ".nomedia"
BACKGROUND_SPRITE_NAME = "Hintergrund"
PACKAGED_PROGRAM_FILE_EXTENSION = ".catrobat"
PROGRAM_SOURCE_FILE_NAME = "code.xml"


def create_lookdata(name, file_name):
    look_data = catcommon.LookData()
    look_data.setLookName(name)
    look_data.setLookFilename(file_name)
    return look_data


def background_sprite_of_project(project):
    if project.getSpriteList().size() > 0:
        sprite = project.getSpriteList().get(0)
        assert sprite.getName() == BACKGROUND_SPRITE_NAME
    else:
        sprite = None
    return sprite

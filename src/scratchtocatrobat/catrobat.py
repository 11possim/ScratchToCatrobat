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
import org.catrobat.catroid.content as catbase

ANDROID_IGNORE_MEDIA_MARKER_FILE_NAME = ".nomedia"
# FIXME: consider localization
BACKGROUND_SPRITE_NAME = "Hintergrund"
MEDIA_LICENSE_URI = "http://developer.catrobat.org/ccbysa_v3"
PACKAGED_PROGRAM_FILE_EXTENSION = catcommon.Constants.CATROBAT_EXTENSION
PROGRAM_LICENSE_URI = "http://developer.catrobat.org/agpl_v3"
PROGRAM_SOURCE_FILE_NAME = catcommon.Constants.PROJECTCODE_NAME


def create_lookdata(name, file_name):
    look_data = catcommon.LookData()
    look_data.setLookName(name)
    look_data.setLookFilename(file_name)
    return look_data


def background_sprite_of(project):
    if project.getSpriteList().size() > 0:
        sprite = project.getSpriteList().get(0)
        assert sprite.getName() == BACKGROUND_SPRITE_NAME
    else:
        sprite = None
    return sprite


def user_variable_of(project, variable_name, sprite_name):
    sprite = None
    for sprite_ in project.getSpriteList():
        if sprite_.getName() == sprite_name:
            sprite = sprite_
            break
    else:
        assert False
    return project.getUserVariables().getUserVariable(variable_name, sprite)


def add_to_start_script(bricks, sprite, position=0):

    def get_or_add_startscript(sprite):
        # HACK: accessing private member, enabled with Jython registry security settings
        for script in sprite.scriptList:
            if isinstance(script, catbase.StartScript):
                return script
        else:
            start_script = catbase.StartScript(sprite)
            sprite.addScript(0, start_script)
            return start_script

    start_script = get_or_add_startscript(sprite)
    start_script.getBrickList().addAll(position, bricks)
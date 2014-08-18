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
from __future__ import unicode_literals

import collections
import itertools
import java
import numbers
import os
import shutil
import types
import zipfile
from codecs import open

import org.catrobat.catroid.common as catcommon
import org.catrobat.catroid.content as catbase
import org.catrobat.catroid.content.bricks as catbricks
import org.catrobat.catroid.formulaeditor as catformula
import org.catrobat.catroid.io as catio

from scratchtocatrobat import catrobat
from scratchtocatrobat import common
from scratchtocatrobat import scratch
from scratchtocatrobat import version
from scratchtocatrobat.scratch import JsonKeys as scratchkeys
from scratchtocatrobat.tools import svgtopng
from scratchtocatrobat.tools import wavconverter

_DEFAULT_BRICK_CLASS = catbricks.WaitBrick
_DEFAULT_FORMULA_ELEMENT = catformula.FormulaElement(catformula.FormulaElement.ElementType.NUMBER, str(00001), None)  # @UndefinedVariable (valueOf)

_GENERATED_VARIABLE_PREFIX = common.APPLICATION_SHORTNAME + ":"
_SOUND_LENGTH_VARIABLE_NAME_FORMAT = "length_of_{}_in_secs"

_SPEAK_BRICK_THINK_INTRO = "I am thinking. "

UNSUPPORTED_SCRATCH_BRICK_NOTE_MESSAGE_PREFIX = "Missing brick for Scratch identifier: "

log = common.log


class ConversionError(common.ScratchtobatError):
        pass


class UnmappedBlock(object):

    def __init__(self, sprite, *args):
        self.sprite = sprite
        self.block_and_args = _with_unmapped_blocks_replaced_as_default_formula_value(args)

    def __str__(self):
        return catrobat.simple_name_for(self.block_and_args)

    def to_placeholder_brick(self):
        return _placeholder_for_unmapped_bricks_to(self.sprite, *self.block_and_args)


def _with_unmapped_blocks_replaced_as_default_formula_value(arguments):
    return [_DEFAULT_FORMULA_ELEMENT if isinstance(argument, UnmappedBlock) else argument for argument in arguments]


def _placeholder_for_unmapped_bricks_to(catr_sprite, *args):
    arguments = ", ".join(map(catrobat.simple_name_for, args))
    return [_DEFAULT_BRICK_CLASS(catr_sprite, 500), catbricks.NoteBrick(catr_sprite, UNSUPPORTED_SCRATCH_BRICK_NOTE_MESSAGE_PREFIX + arguments)]


def _key_to_broadcast_message(key_name):
    return "key " + key_name + " pressed"


def _background_look_to_broadcast_message(look_name):
    return "start background scene: " + look_name


def _next_background_look_broadcast_message():
    return "set background to next look"


def _sec_to_msec(duration):
    return duration * 1000


# note: for Scratch blocks without mapping placeholder Catrobat bricks will be added
class _ScratchToCatrobat(object):

    compute_block_parameters_mapping = {
        "abs": catformula.Functions.ABS,
        "sqrt": catformula.Functions.SQRT,
        "sin": catformula.Functions.SIN,
        "cos": catformula.Functions.COS,
        "tan": catformula.Functions.TAN,
        "asin": catformula.Functions.ARCSIN,
        "acos": catformula.Functions.ARCCOS,
        "atan": catformula.Functions.ARCTAN,
        "e^": catformula.Functions.EXP,
        "ln": catformula.Functions.LN,
        "log": catformula.Functions.LOG,
        "rounded": catformula.Functions.ROUND,
        "randomFrom:to:": catformula.Functions.RAND,
        "%": catformula.Functions.MOD,
        #  TODO:
        # "10^"
        # "floor"
        # "ceiling"
    }

    unary_operators_mapping = {
        "not": catformula.Operators.LOGICAL_NOT,
    }

    operators_mapping = dict({
        "+": catformula.Operators.PLUS,
        "-": catformula.Operators.MINUS,
        "*": catformula.Operators.MULT,
        "/": catformula.Operators.DIVIDE,
        "<": catformula.Operators.SMALLER_THAN,
        "=": catformula.Operators.EQUAL,
        ">": catformula.Operators.GREATER_THAN,
        "&": catformula.Operators.LOGICAL_AND,
        "|": catformula.Operators.LOGICAL_OR,
    }.items() + unary_operators_mapping.items())

    complete_mapping = dict({
        #
        # Scripts
        #
        "whenGreenFlag": catbase.StartScript,
        "whenIReceive": catbase.BroadcastScript,
        "whenKeyPressed": lambda sprite, key: catbase.BroadcastScript(sprite, _key_to_broadcast_message(key)),
        # TODO: "whenSensorGreaterThan"
        "whenSceneStarts": lambda sprite, look_name: catbase.BroadcastScript(sprite, _background_look_to_broadcast_message(look_name)),
        "whenClicked": catbase.WhenScript,

        #
        # Bricks
        #
        "broadcast:": catbricks.BroadcastBrick,
        "doBroadcastAndWait": catbricks.BroadcastWaitBrick,
        # TODO: creation method for FormulaElement object
        "wait:elapsed:from:": lambda sprite, duration: catbricks.WaitBrick(sprite, catformula.Formula(duration)),

        # conditionals
        "doForever": catbricks.ForeverBrick,
        # FIXME: dummy value
        "doIf": "dummy",  # [catbricks.IfLogicBeginBrick, catbricks.IfLogicEndBrick],
        "doIfElse": "dummy",  # [catbricks.IfLogicBeginBrick, catbricks.IfLogicElseBrick, catbricks.IfLogicEndBrick],
        "doRepeat": catbricks.RepeatBrick,
        "doUntil": "dummy",
        "doWaitUntil": "dummy",

        "turnRight:": catbricks.TurnRightBrick,
        "turnLeft:": catbricks.TurnLeftBrick,
        "heading:": catbricks.PointInDirectionBrick,
        "forward:": catbricks.MoveNStepsBrick,
        "pointTowards:": catbricks.PointToBrick,
        "gotoX:y:": catbricks.PlaceAtBrick,
        "glideSecs:toX:y:elapsed:from:": lambda sprite, duration, x_pos, y_pos: catbricks.GlideToBrick(sprite, x_pos, y_pos, _sec_to_msec(duration) if isinstance(duration, numbers.Number) else duration),
        "xpos:": catbricks.SetXBrick,
        "ypos:": catbricks.SetYBrick,
        "bounceOffEdge": catbricks.IfOnEdgeBounceBrick,
        "changeXposBy:": catbricks.ChangeXByNBrick,
        "changeYposBy:": catbricks.ChangeYByNBrick,

        # variables
        "setVar:to:": lambda *args: _create_variable_brick(*itertools.chain(args, [catbricks.SetVariableBrick])),
        "changeVar:by:": lambda *args: _create_variable_brick(*itertools.chain(args, [catbricks.ChangeVariableBrick])),
        "readVariable": lambda _, variable_name: _variable_for(variable_name),

        # looks
        "lookLike:": catbricks.SetLookBrick,
        "nextCostume": catbricks.NextLookBrick,
        "startScene": catbricks.BroadcastBrick,
        "nextScene": catbricks.NextLookBrick,  # only allowed in scene object so same as nextLook

        # TODO: remove lambdas to increase readability
        "changeGraphicEffect:by:": lambda sprite, effect_type, value:
            catbricks.ChangeBrightnessByNBrick(sprite, value) if effect_type == 'brightness' else
            catbricks.ChangeGhostEffectByNBrick(sprite, value) if effect_type == 'ghost' else
            _placeholder_for_unmapped_bricks_to(sprite, effect_type, value),
        "setGraphicEffect:to:": lambda sprite, effect_type, value:
            catbricks.SetBrightnessBrick(sprite, value) if effect_type == 'brightness' else
            catbricks.SetGhostEffectBrick(sprite, value) if effect_type == 'ghost' else
            _placeholder_for_unmapped_bricks_to(sprite, effect_type, value),
        "filterReset": catbricks.ClearGraphicEffectBrick,
        "changeSizeBy:": catbricks.ChangeSizeByNBrick,
        "setSizeTo:": catbricks.SetSizeToBrick,
        "show": catbricks.ShowBrick,
        "hide": catbricks.HideBrick,
        "comeToFront": catbricks.ComeToFrontBrick,
        "goBackByLayers:": catbricks.GoNStepsBackBrick,

        # sound
        "playSound:": catbricks.PlaySoundBrick,
        "doPlaySoundAndWait": catbricks.PlaySoundBrick,
        "stopAllSounds": catbricks.StopAllSoundsBrick,
        "changeVolumeBy:": catbricks.ChangeVolumeByNBrick,
        "setVolumeTo:": catbricks.SetVolumeToBrick,

        # TODO: "\\\\"

        # sprite values
        "xpos": catformula.Sensors.OBJECT_X,
        "ypos": catformula.Sensors.OBJECT_Y,
        "heading": catformula.Sensors.OBJECT_ROTATION,
        "size": catformula.Sensors.OBJECT_SIZE,

        # sensors
        # WORKAROUND: using ROUND for Catrobat float => Scratch int
        "soundLevel": lambda *_args: catrobat.formula_element_for(catformula.Functions.ROUND, arguments=[catrobat.formula_element_for(catformula.Sensors.LOUDNESS)]),
    }.items() + compute_block_parameters_mapping.items() + operators_mapping.items())

    # TODO: check if necessary
    parameters = {
        "brightness",
        "color",  # unsupported
        "ghost",
    }

    @classmethod
    def catrobat_brick_class_for(cls, scratch_block_name):
        assert isinstance(scratch_block_name, (str, unicode))
        catrobat_brick = cls.complete_mapping.get(scratch_block_name)
        if isinstance(catrobat_brick, types.LambdaType):
            catrobat_brick.__name__ = scratch_block_name + "-lambda"
        return catrobat_brick

    @classmethod
    def create_script(cls, scratch_script_name, sprite, arguments):
        assert sprite is not None
        if scratch_script_name not in scratch.SCRIPTS:
            assert False, "Missing script mapping for: " + scratch_script_name
        # TODO: separate script and brick mapping
        return cls.catrobat_brick_class_for(scratch_script_name)(sprite, *arguments)


def _create_variable_brick(sprite, value, user_variable, Class):
    assert Class in set([catbricks.SetVariableBrick, catbricks.ChangeVariableBrick])

    def catrobat_formula_from(variable_value):
        # TODO: verify general correctness
        if not variable_value:
            variable_value = 0
        elif isinstance(variable_value, (str, unicode)):
            try:
                variable_value = common.int_or_float(variable_value)
            except:
                log.warning("Ignoring unsupported variable value: '%s'. Set to 0.", variable_value)
                variable_value = 0

        if type(variable_value) is int:
            java_variable_value = java.lang.Integer(variable_value)
        elif isinstance(variable_value, (float, long)):
            java_variable_value = java.lang.Double(variable_value)
        else:
            assert isinstance(variable_value, catformula.FormulaElement), variable_value
            java_variable_value = variable_value

        return catformula.Formula(java_variable_value)

    return Class(sprite, catrobat_formula_from(value), user_variable)


def _variable_for(variable_name):
    return catformula.FormulaElement(catformula.FormulaElement.ElementType.USER_VARIABLE, variable_name, None)  # @UndefinedVariable


def _key_image_path_for(key):
    key_images_path = os.path.join(common.get_project_base_path(), 'resources', 'key_images')
    for key_filename in os.listdir(key_images_path):
        basename, _ = os.path.splitext(key_filename)
        if basename.lower().endswith(" ".join(key.split())):
            return os.path.join(key_images_path, key_filename)


def _key_filename_for(key):
    assert key is not None
    key_path = _key_image_path_for(key)
    # TODO: extract method, already used once
    return common.md5_hash(key_path) + "_" + _key_to_broadcast_message(key) + os.path.splitext(key_path)[1]


def _update_xml_header(xml_header, scratch_project):
    xml_header.setApplicationBuildName("*** TODO ***")
    xml_header.setApplicationName(common.APPLICATION_NAME)
    xml_header.setApplicationVersion(version.__version__)
    xml_header.setCatrobatLanguageVersion(catcommon.Constants.CURRENT_CATROBAT_LANGUAGE_VERSION)
    xml_header.setDescription(scratch_project.description)
    xml_header.setDeviceName("Scratch")
    xml_header.setPlatform("Scratch")
    # TODO: platform version should allow float
    xml_header.setPlatformVersion(2)
    xml_header.setScreenMode(catcommon.ScreenModes.MAXIMIZE)
    xml_header.mediaLicense = catrobat.MEDIA_LICENSE_URI
    xml_header.programLicense = catrobat.PROGRAM_LICENSE_URI
    if scratch_project.project_id is not None:
        xml_header.remixOf = scratch.HTTP_PROJECT_URL_PREFIX + scratch_project.project_id

_catr_project = None


def catrobat_program_from(scratch_project):
    global _catr_project
    _catr_project = catbase.Project(None, scratch_project.name)
    _catr_project.getXmlHeader().virtualScreenHeight = scratch.STAGE_HEIGHT_IN_PIXELS
    _catr_project.getXmlHeader().virtualScreenWidth = scratch.STAGE_WIDTH_IN_PIXELS
    for object_ in scratch_project.objects:
        catr_sprite = _catrobat_sprite_from(object_)
        if object_ is scratch_project.stage_object:
            catr_sprite.setName(catrobat.BACKGROUND_SPRITE_NAME)
        _catr_project.addSprite(catr_sprite)


def _sound_length_variable_name_for(resource_name):
    return _generated_variable_name(_SOUND_LENGTH_VARIABLE_NAME_FORMAT.format(resource_name))


def _is_generated(variable_name):
    return variable_name.startswith(_GENERATED_VARIABLE_PREFIX)


    # TODO: make it more explicit that this depends on the conversion code for "whenKeyPressed" Scratch block
    def add_used_key_sprites(listened_keys, catrobat_project):
        height_pos = 1
        for idx, key in enumerate(listened_keys):
            width_pos = idx
            key_filename = _key_filename_for(key)
            key_message = _key_to_broadcast_message(key)

            key_sprite = catbase.Sprite(key_message)
            key_look = catcommon.LookData()
            key_look.setLookName(key_message)
            key_look.setLookFilename(key_filename)
            key_sprite.getLookDataList().add(key_look)

            # initialize key images in left upper corner
            when_started_script = catbase.StartScript(key_sprite)
            set_look_brick = catbricks.SetLookBrick(key_sprite)
            set_look_brick.setLook(key_look)

            # special handling wider button
            if key == "space":
                width_pos = 0
                height_pos = 2
            y_pos = (scratch.STAGE_HEIGHT_IN_PIXELS / 2) - 40 * height_pos
            x_pos = -(scratch.STAGE_WIDTH_IN_PIXELS / 2) + 40 * (width_pos + 1)
            place_at_brick = catbricks.PlaceAtBrick(key_sprite, x_pos, y_pos)

            bricks = [place_at_brick, set_look_brick, catbricks.SetSizeToBrick(key_sprite, 33)]
            when_started_script.getBrickList().addAll(bricks)
            key_sprite.addScript(when_started_script)

            when_tapped_script = catbase.WhenScript(key_sprite)
            when_tapped_script.addBrick(catbricks.BroadcastBrick(key_sprite, key_message))
            key_sprite.addScript(when_tapped_script)

            catrobat_project.addSprite(key_sprite)

    add_used_key_sprites(scratch_project.listened_keys, _catr_project)
    _update_xml_header(_catr_project.getXmlHeader(), scratch_project)
    return _catr_project


def _catrobat_sprite_from(scratch_object):
    if not isinstance(scratch_object, scratch.Object):
        raise common.ScratchtobatError("Input must be of type={}, but is={}".format(scratch.Object, type(scratch_object)))
    sprite = catbase.Sprite(scratch_object.get_objName())

    sprite_looks = sprite.getLookDataList()
    costume_resolution = None
    for scratch_costume in scratch_object.get_costumes():
        current_costume_resolution = scratch_costume.get(scratchkeys.COSTUME_RESOLUTION)
        if not costume_resolution:
            costume_resolution = current_costume_resolution
        else:
            if current_costume_resolution != costume_resolution:
                log.warning("Costume resolution not same for all costumes")
        sprite_looks.add(_catrobat_look_from(scratch_costume))

    sprite_sounds = sprite.getSoundList()
    for scratch_sound in scratch_object.get_sounds():
        sprite_sounds.add(_catrobat_sound_from(scratch_sound))

    # looks and sounds has to added first because of cross-validations
    for scratch_script in scratch_object.scripts:
        sprite.addScript(_catrobat_script_from(scratch_script, sprite))

    def add_initial_scratch_object_behaviour():
        # some initial Scratch settings are done with a general JSON configuration instead with blocks. Here the equivalent bricks are added for Catrobat.
        implicit_bricks_to_add = []

        # object's currentCostumeIndex determines active costume at startup
        sprite_startup_look_idx = scratch_object.get_currentCostumeIndex()
        if sprite_startup_look_idx is not None:
            spriteStartupLook = sprite.getLookDataList()[sprite_startup_look_idx]
            set_look_brick = catbricks.SetLookBrick(sprite)
            set_look_brick.setLook(spriteStartupLook)
            implicit_bricks_to_add += [set_look_brick]

        # object's scratchX and scratchY Keys determine position
        x_pos = scratch_object.get_scratchX() or 0
        y_pos = scratch_object.get_scratchY() or 0
        place_at_brick = catbricks.PlaceAtBrick(sprite, int(x_pos), int(y_pos))
        implicit_bricks_to_add += [place_at_brick]

        object_scale = scratch_object.get_scale() or 1
        implicit_bricks_to_add += [catbricks.SetSizeToBrick(sprite, object_scale * 100.0 / costume_resolution)]

        object_direction = scratch_object.get_direction() or 90
        implicit_bricks_to_add += [catbricks.PointInDirectionBrick(sprite, object_direction)]

        object_visible = scratch_object.get_visible()
        if object_visible is not None and not object_visible:
            implicit_bricks_to_add += [catbricks.HideBrick(sprite)]

        rotation_style = scratch_object.get_rotationStyle()
        if rotation_style and rotation_style != "normal":
            log.warning("Unsupported rotation style '{}' at object: {}".format(rotation_style, scratch_object.get_objName()))

        catrobat.add_to_start_script(implicit_bricks_to_add, sprite)

    add_initial_scratch_object_behaviour()
    return sprite


def _catrobat_script_from(scratch_script, sprite):
    if not isinstance(scratch_script, scratch.Script):
        raise common.ScratchtobatError("Arg1 must be of type={}, but is={}".format(scratch.Script, type(scratch_script)))
    if sprite and not isinstance(sprite, catbase.Sprite):
        raise common.ScratchtobatError("Arg2 must be of type={}, but is={}".format(catbase.Sprite, type(sprite)))

    cat_script = _ScratchToCatrobat.create_script(scratch_script.type, sprite, scratch_script.arguments)
    for scratch_block in scratch_script.blocks:
        cat_bricks = _catrobat_bricks_from(scratch_block, sprite)
        for brick in cat_bricks:
            cat_script.addBrick(brick)
    return cat_script


def _catrobat_look_from(scratch_costume):
    if not scratch_costume or not (isinstance(scratch_costume, dict) and all(_ in scratch_costume for _ in (scratchkeys.COSTUME_MD5, scratchkeys.COSTUME_NAME))):
        raise common.ScratchtobatError("Wrong input, must be costume dict: {}".format(scratch_costume))
    look = catcommon.LookData()

    assert scratchkeys.COSTUME_NAME in scratch_costume
    costume_name = scratch_costume[scratchkeys.COSTUME_NAME]
    look.setLookName(costume_name)

    assert scratchkeys.COSTUME_MD5 in scratch_costume
    costume_filename = scratch_costume[scratchkeys.COSTUME_MD5]
    costume_filename_ext = os.path.splitext(costume_filename)[1]
    look.setLookFilename(costume_filename.replace(costume_filename_ext, "_" + costume_name + costume_filename_ext))
    return look


def _catrobat_sound_from(scratch_sound):
    soundinfo = catcommon.SoundInfo()

    assert scratchkeys.SOUND_NAME in scratch_sound
    sound_name = scratch_sound[scratchkeys.SOUND_NAME]
    soundinfo.setTitle(sound_name)

    assert scratchkeys.SOUND_MD5 in scratch_sound
    sound_filename = scratch_sound[scratchkeys.SOUND_MD5]
    sound_filename_ext = os.path.splitext(sound_filename)[1]
    soundinfo.setSoundFileName(sound_filename.replace(sound_filename_ext, "_" + sound_name + sound_filename_ext))
    return soundinfo


def converted_output_path(output_dir, project_name):
    return os.path.join(output_dir, project_name + catrobat.PACKAGED_PROGRAM_FILE_EXTENSION)


def save_as_catrobat_program_package_to(scratch_project, output_dir):
    def iter_dir(path):
        for root, _, files in os.walk(path):
            for file_ in files:
                yield os.path.join(root, file_)
    log.info("convert Scratch project to '%s'", output_dir)
    with common.TemporaryDirectory() as catrobat_program_dir:
        save_as_catrobat_program_to(scratch_project, catrobat_program_dir)
        common.makedirs(output_dir)
        catrobat_zip_file_path = converted_output_path(output_dir, scratch_project.name)
        if os.path.exists(catrobat_zip_file_path):
            shutil.rmtree(catrobat_zip_file_path)
        with zipfile.ZipFile(catrobat_zip_file_path, 'w') as zip_fp:
            for file_path in iter_dir(unicode(catrobat_program_dir)):
                assert isinstance(file_path, unicode)
                path_inside_zip = file_path.replace(catrobat_program_dir, u"")
                zip_fp.write(file_path, path_inside_zip)
        assert zip_fp.fp is None or zip_fp.fp.closed

    return catrobat_zip_file_path


def images_dir_of_project(temp_dir):
    return os.path.join(temp_dir, "images")


def sounds_dir_of_project(temp_dir):
    return os.path.join(temp_dir, "sounds")


# TODO: change to OO
def save_as_catrobat_program_to(scratch_project, temp_path):

    def create_directory_structure():
        sounds_path = sounds_dir_of_project(temp_path)
        os.mkdir(sounds_path)

        images_path = images_dir_of_project(temp_path)
        os.mkdir(images_path)

        for _ in (temp_path, sounds_path, images_path):
            # TODO: into common module
            open(os.path.join(_, catrobat.ANDROID_IGNORE_MEDIA_MARKER_FILE_NAME), 'a').close()
        return sounds_path, images_path

    def write_mediafiles():
        def resource_name_for(file_path):
            return common.md5_hash(file_path) + os.path.splitext(file_path)[1]

        # FIXME: modifies Scratch project object
        def update_resource_name(old_resource_name, new_resource_name):
            resource_maps = list(scratch_project.find_all_resource_dicts_for(old_resource_name))
            assert len(resource_maps) > 0
            for resource_map in resource_maps:
                if scratchkeys.COSTUME_MD5 in resource_map:
                    resource_map[scratchkeys.COSTUME_MD5] = new_resource_name
                elif scratchkeys.SOUND_MD5 in resource_map:
                    resource_map[scratchkeys.SOUND_MD5] = new_resource_name
                else:
                    assert False, "Unknown dict: {}".resource_map

        for scratch_md5_name, src_path in scratch_project.md5_to_resource_path_map.iteritems():
            if scratch_md5_name in scratch_project.unused_resource_names:
                log.info("Ignoring unused resource file: %s", src_path)
                continue

            file_ext = os.path.splitext(scratch_md5_name)[1].lower()
            converted_file = False

            # TODO; extract method
            if file_ext in {".png", ".svg", ".jpg", ".gif"}:
                target_dir = images_path

                if file_ext == ".svg":
                    # converting svg to png -> new md5 and filename
                    src_path = svgtopng.convert(src_path)
                    if not os.path.exists(src_path):
                        assert False, "Not existing: {}. Available files in directory: {}".format(src_path, os.listdir(os.path.dirname(src_path)))
                    converted_file = True

            elif file_ext in {".wav", ".mp3"}:
                target_dir = sounds_path
                if file_ext == ".wav":
                    if not wavconverter.is_android_compatible_wav(src_path):
                        temp_path = src_path.replace(".wav", "converted.wav")
                        wavconverter.convert_to_android_compatible_wav(src_path, temp_path)
                        src_path = temp_path
                        converted_file = True

            else:
                assert file_ext in {".json"}, "Unknown media file extension: %s" % src_path
                continue

            assert os.path.exists(src_path), "Not existing: {}. Available files in directory: {}".format(src_path, os.listdir(os.path.dirname(src_path)))
            if converted_file:
                new_resource_name = resource_name_for(src_path)
                update_resource_name(scratch_md5_name, new_resource_name)
                scratch_md5_name = new_resource_name
            # separate file name for each sprite in which a resource is used
            for catrobat_file_name in _catrobat_resource_file_name_for(scratch_md5_name, scratch_project):
                shutil.copyfile(src_path, os.path.join(target_dir, catrobat_file_name))
            if converted_file:
                os.remove(src_path)

    def program_source_for(catrobat_program):
        storage_handler = catio.StorageHandler()
        code_xml_content = storage_handler.XML_HEADER
        code_xml_content += storage_handler.getXMLStringOfAProject(catrobat_program)
        return code_xml_content

    def write_program_source():
        catrobat_program = catrobat_program_from(scratch_project)

        # TODO: extract method
        # note: at this position because of use of sounds_path variable
        # adding sound length variables needed for "doPlayAndWait" brick workaround
        sprite_to_variable_initializations_map = collections.defaultdict(list)
        for catrobat_sprite in catrobat_program.getSpriteList():
            for sound_info in catrobat_sprite.getSoundList():
                sound_length = common.length_of_audio_file_in_msec(os.path.join(sounds_path, sound_info.getSoundFileName()))
                variable = catrobat_program.getUserVariables().addSpriteUserVariableToSprite(catrobat_sprite, _sound_length_variable_name_for(sound_info.getTitle()))
                print catrobat_sprite.getName(), variable.getName()
                sprite_to_variable_initializations_map[catrobat_sprite] += [(variable, sound_length)]
        print sprite_to_variable_initializations_map
        for sprite, variable_initializations in sprite_to_variable_initializations_map.iteritems():
            variable_initialization_bricks = [catbricks.SetVariableBrick(sprite, catformula.Formula(value), variable) for variable, value in variable_initializations]
            catrobat.add_to_start_script(variable_initialization_bricks, sprite)

        program_source = program_source_for(catrobat_program)
        with open(os.path.join(temp_path, catrobat.PROGRAM_SOURCE_FILE_NAME), "wb") as fp:
            fp.write(program_source.encode("utf8"))

        # copying key images needed for keyPressed substitution
        for listened_key in scratch_project.listened_keys:
            key_image_path = _key_image_path_for(listened_key)
            shutil.copyfile(key_image_path, os.path.join(images_path, _key_filename_for(listened_key)))

    # TODO: rename/rearrange abstracting methods
    log.info("  Creating Catrobat project structure")
    sounds_path, images_path = create_directory_structure()
    log.info("  Saving media files")
    write_mediafiles()
    log.info("  Saving project XML file")
    write_program_source()


# TODO: could be done with just user_variables instead of project object
def _add_new_variable_with_initialization_value(project, variable_name, variable_value, sprite, sprite_name=None):
    user_variable = catrobat.add_user_variable(project, variable_name, sprite=sprite, sprite_name=sprite_name)
    assert user_variable is not None
    variable_initialization_brick = _create_variable_brick(sprite, variable_value, user_variable, catbricks.SetVariableBrick)
    catrobat.add_to_start_script([variable_initialization_brick], sprite)


def _catrobat_resource_file_names_for(scratch_md5_name, scratch_project):
    assert os.path.basename(scratch_md5_name) == scratch_md5_name and len(os.path.splitext(scratch_md5_name)[0]) == 32, "Must be MD5 hash with file ext: " + scratch_md5_name
    catrobat_resource_names = []
    for resource in scratch_project.find_all_resource_dicts_for(scratch_md5_name):
        if resource:
            try:
                resource_name = resource[scratchkeys.SOUND_NAME] if scratchkeys.SOUND_NAME in resource else resource[scratchkeys.COSTUME_NAME]
            except KeyError:
                raise ConversionError("Error with: {}, {}".format(scratch_md5_name, resource))
            resource_ext = os.path.splitext(scratch_md5_name)[1]
            catrobat_resource_names += [scratch_md5_name.replace(resource_ext, "_" + resource_name + resource_ext)]
    assert len(catrobat_resource_names) != 0, "{} not found (path: {}). available: {}".format(scratch_md5_name, scratch_project.md5_to_resource_path_map.get(scratch_md5_name), scratch_project.resource_names)
    return catrobat_resource_names


# based on: http://stackoverflow.com/a/4274204
def _register_handler(dict_, *names):
    def dec(f):
        m_name = f.__name__
        for name in names:
            dict_[name] = m_name
        return f
    return dec


class _BlocksConversionTraverser(scratch.AbstractBlocksTraverser):

    _block_name_to_handler_map = {}

    def __init__(self, catrobat_sprite, catrobat_project):
        assert catrobat_sprite is not None
        assert catrobat_project is not None
        self.sprite = catrobat_sprite
        self.project = catrobat_project
        self._stack = []

    @property
    def stack(self):
        return self.converted_bricks

    @property
    def converted_bricks(self):
        return self._stack

    def traverse(self, script_element):
        self._stack += [script_element.name]
        super(_BlocksConversionTraverser, self).traverse(script_element)

    def _pop_stack(self, start_index):
        popped = list(self._stack[start_index:])
        del self._stack[start_index:]
        return popped

    def _visit(self, script_element):
        self.script_element = script_element
        arguments_start_index = len(self._stack) - self._stack[::-1].index(script_element.name)
        self.arguments = self._pop_stack(arguments_start_index)

        new_stack_values = self._converted_script_element()
        del self._stack[-1]
        if not isinstance(new_stack_values, list):
            new_stack_values = [new_stack_values]
        self._stack += new_stack_values

    def _converted_script_element(self):
        script_element = self.script_element
        if script_element.name == "computeFunction:of:":
            # removing block name which is common prefix for all function blocks:
            # [Block("computeFunction:of:"), BlockValue("tan"), ...] is changed to [Block("tan"), ...]
            assert len(self.arguments) >= 1
            self.script_element = scratch.Block(name=self.arguments[0])
            self.arguments = self.arguments[1:]
        self.block_name = block_name = self.script_element.name
        if isinstance(self.script_element, scratch.Block):
            log.debug("    block to convert: %s, arguments: %s", block_name, catrobat.simple_name_for(self.arguments))
            self.CatrobatClass = _ScratchToCatrobat.catrobat_brick_class_for(block_name)
            handler_method_name = self._block_name_to_handler_map.get(block_name)
            if handler_method_name is not None:
                converted_element = getattr(self, handler_method_name)()
            else:
                converted_element = self._regular_block_conversion()
        elif isinstance(self.script_element, scratch.BlockValue):
            converted_element = [script_element.name]
        else:
            assert isinstance(self.script_element, scratch.BlockList)
            # TODO: readability
            converted_element = [[arg2 for arg1 in self.arguments for arg2 in (arg1.to_placeholder_brick() if isinstance(arg1, UnmappedBlock) else [arg1])]]
        return converted_element

    def _regular_block_conversion(self):
        CatrobatClass = self.CatrobatClass
        # TODO: replace with UnmappedBlock as a None object
        if CatrobatClass is not None:
            is_catrobat_enum = not hasattr(CatrobatClass, "__module__") and hasattr(CatrobatClass, "getClass")
            self.arguments = _with_unmapped_blocks_replaced_as_default_formula_value(self.arguments)
            for try_number in range(6):
                try:
                    # TODO: simplify
                    if try_number == 0:
                        converted_args = [common.int_or_float(arg) or arg if isinstance(arg, (str, unicode)) else arg for arg in self.arguments]
                    elif try_number == 1:
                        converted_args = [catformula.FormulaElement(catformula.FormulaElement.ElementType.NUMBER, str(arg), None) if isinstance(arg, numbers.Number) else arg for arg in converted_args]  # @UndefinedVariable
                    elif try_number == 4:
                        converted_args = self.arguments
                    elif try_number == 2:
                        converted_args = [catformula.Formula(arg) for arg in self.arguments]
                    elif try_number == 3:
                        if len(self.arguments) == 2 and self.arguments[0] in _ScratchToCatrobat.parameters:
                            converted_args = [self.arguments[0]] + [catformula.Formula(arg) for arg in self.arguments[1:]]

                    if not is_catrobat_enum:
                        converted_value = CatrobatClass(self.sprite, *converted_args)
                    else:
                        converted_value = catrobat.formula_element_for(CatrobatClass, converted_args)
                    assert converted_value, "No result for {} with args {}".format(self.block_name, converted_args)
                    break
                except (TypeError) as e:
                    log.debug("instantiation try %d failed for class: %s, raw_args: %s, Catroid args: %s", try_number, CatrobatClass, self.arguments, map(catrobat.simple_name_for, converted_args))
                    class_exception = e
            else:
                log.error("General instantiation failed for class: %s, raw_args: %s, Catroid args: %s", CatrobatClass, self.arguments, map(catrobat.simple_name_for, converted_args))
                raise class_exception
                log.exception(class_exception)
                self.errors += [class_exception]
            new_stack_values = converted_value
        else:
            log.debug("no Class for: %s, args: %s", self.block_name, map(catrobat.simple_name_for, self.arguments))
            new_stack_values = UnmappedBlock(self.sprite, *([self.block_name] + self.arguments))
        return new_stack_values

    @_register_handler(_block_name_to_handler_map, "doRepeat", "doForever")
    def _convert_loop_blocks(self):
        brick_arguments = self.arguments
        self.block_name = self.block_name
        if self.block_name == 'doRepeat':
            times_value, nested_bricks = brick_arguments
            catr_loop_start_brick = self.CatrobatClass(self.sprite, catformula.Formula(times_value))
        else:
            assert self.block_name == 'doForever', self.block_name
            [nested_bricks] = brick_arguments
            catr_loop_start_brick = self.CatrobatClass(self.sprite)
        return [catr_loop_start_brick] + nested_bricks + [catbricks.LoopEndBrick(self.sprite, catr_loop_start_brick)]

    @_register_handler(_block_name_to_handler_map, "startScene")
    def _convert_scene_block(self):
        catr_bricks = []
        self.sprite = self.sprite
        catrobat_brick_class = self.CatrobatClass

        [look_name] = self.arguments
        background_sprite = catrobat.background_sprite_of(self.project)
        if not background_sprite:
            assert catrobat.is_background_sprite(self.sprite)
            background_sprite = self.sprite
        matching_looks = [_ for _ in background_sprite.getLookDataList() if _.getLookName() == look_name]
        if not matching_looks:
            raise ConversionError("Background does not contain look with name: {}".format(look_name))
        assert len(matching_looks) == 1
        [matching_look] = matching_looks
        look_message = _background_look_to_broadcast_message(look_name)
        broadcast_brick = catrobat_brick_class(self.sprite, look_message)
        catr_bricks += [broadcast_brick]

        broadcast_script = catbase.BroadcastScript(background_sprite, look_message)
        set_look_brick = catbricks.SetLookBrick(background_sprite)
        set_look_brick.setLook(matching_look)
        broadcast_script.addBrick(set_look_brick)
        background_sprite.addScript(broadcast_script)

        return catr_bricks

    @_register_handler(_block_name_to_handler_map, "doIf", "doIfElse")
    def _convert_if_block(self):
        if_begin_brick = catbricks.IfLogicBeginBrick(self.sprite, catformula.Formula(self.arguments[0]))
        if_else_brick = catbricks.IfLogicElseBrick(self.sprite, if_begin_brick)
        if_end_brick = catbricks.IfLogicEndBrick(self.sprite, if_else_brick, if_begin_brick)
        assert 2 <= len(self.arguments) <= 3
        if_bricks, [else_bricks] = self.arguments[1], self.arguments[2:] or [[]]
        return [if_begin_brick] + if_bricks + [if_else_brick] + else_bricks + [if_end_brick]

    @_register_handler(_block_name_to_handler_map, "lookLike:")
    def _convert_look_block(self):
        set_look_brick = self.CatrobatClass(self.sprite)
        [look_name] = self.arguments
        assert isinstance(look_name, (str, unicode)), type(look_name)
        look = next((look for look in self.sprite.getLookDataList() if look.getLookName() == look_name), None)
        if look is None:
            log.error("Look name: '%s' not found in sprite '%s'. Available looks: %s", look_name, self.sprite.getName(), ", ".join([look.getLookName() for look in self.sprite.getLookDataList()]))
            return []
        else:
            set_look_brick.setLook(look)
            return [set_look_brick]

    @_register_handler(_block_name_to_handler_map, "playSound:", "doPlaySoundAndWait")
    def _convert_sound_block(self):
        self.sprite = self.sprite
        [sound_name] = self.arguments
        soundinfo_name_to_soundinfo_map = {lookdata.getTitle(): lookdata for lookdata in self.sprite.getSoundList()}
        lookdata = soundinfo_name_to_soundinfo_map.get(sound_name)
        if not lookdata:
            raise ConversionError("Sprite does not contain sound with name={}".format(sound_name))
        play_sound_brick = self.CatrobatClass(self.sprite)
        play_sound_brick.setSoundInfo(lookdata)
        catr_bricks = [play_sound_brick]
        if self.block_name == "doPlaySoundAndWait":
            sound_length_variable = _variable_for(_sound_length_variable_name_for(sound_name))
            catr_bricks += [catbricks.WaitBrick(self.sprite, catformula.Formula(sound_length_variable))]
        return catr_bricks

    @_register_handler(_block_name_to_handler_map, "changeVar:by:", "setVar:to:")
    def _convert_variable_block(self):
        variable_name, value = self.arguments
        user_variable = self.project.getUserVariables().getUserVariable(variable_name, self.sprite)
        if user_variable is None and _is_generated(variable_name):
            # WORKAROUND: for generated variables added in preprocessing step (e.g doUntil rewrite)
            catrobat.add_user_variable(self.project, variable_name, self.sprite, self.sprite.getName())
            user_variable = self.project.getUserVariables().getUserVariable(variable_name, self.sprite)
            assert user_variable is not None and user_variable.getName() == variable_name, "variable: %s, sprite_name: %s" % (variable_name, self.sprite.getName())
        return [self.CatrobatClass(self.sprite, value, user_variable)]

    @_register_handler(_block_name_to_handler_map, "say:duration:elapsed:from:", "say:", "think:duration:elapsed:from:", "think:")
    def _convert_say_think_blocks(self):
        text, _args = self.arguments[0], self.arguments[1:]
        if self.block_name.startswith("think:"):
            text = _SPEAK_BRICK_THINK_INTRO + text
        # FIXME: value should depend on text length and optionally args
        return [catbricks.SpeakBrick(self.sprite, text), catbricks.WaitBrick(self.sprite, 1000)]

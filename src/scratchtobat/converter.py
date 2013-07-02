from codecs import open
from scratchtobat import catrobatwriter as sb2keys, common, sb2
from scratchtobat.tools import svgtopng
import hashlib
import org.catrobat.catroid.common as catcommon
import org.catrobat.catroid.content as catbase
import org.catrobat.catroid.content.bricks as catbricks
import org.catrobat.catroid.io as catio
import os
import shutil
import tempfile
import zipfile

CATROID_PROJECT_FILE = "code.xml"
CATROID_NOMEDIA_FILE = ".nomedia"

# based on: http://code.google.com/p/sb2-js/source/browse/trunk/editor.htm
SCRATCH_TO_CATROBAT_MAPPING = {
     # keys with value=None will be converted to WaitBrick with 500 ms
    #===========================================================================
    # Scripts
    #===========================================================================
    "whenGreenFlag": catbase.StartScript,
    "whenIReceive": catbase.BroadcastScript,
    "whenKeyPressed": lambda sprite, key: catbase.BroadcastScript(sprite, _keyPressedToBroadcastMessage(key)),
    "whenSensorGreaterThan": None,
    "whenSceneStarts": None,  # easy: stage msg broadcast
    # easy: missing whenSpriteClicked
    
    #===============================================================================
    #  Bricks  
    #===============================================================================
    "broadcast:": None,  # easy
    "doReturn": None,
    "doWaitUntil": None,
    "wait:elapsed:from:": lambda sprite, time_value: catbricks.WaitBrick(sprite, int(time_value * 1000)),
    "stopAll": None,
    "stopScripts": None,
    
    # conditionals
    "doForever": catbricks.ForeverBrick,
    "doIf": None,  # easy
    "doIfElse": None,  # easy
    "doRepeat": catbricks.RepeatBrick,
    "doUntil": None,
    
    "turnRight:": None,  # easy
    "turnLeft:": None,  # easy
    "heading:": None,  # easy
    "forward:": catbricks.MoveNStepsBrick,
    "pointTowards:": None,  # easy
    "gotoX:y:": None,  # easy
   # "xpos:": None, # easy
   # "ypos:": None, # easy
    "glideSecs:toX:y:elapsed:from:": None,  # easy
    "changeXposBy:": None,  # easy
    "changeYposBy:": None,  # easy
    "bounceOffEdge": None,  # easy (screen as now)
    
    # variables
    "setVar:to:": None,  # easy
    "changeVar:by:": None,  # easy
    "showVariable:": None,
    "hideVariable:": None,
    
    # lists
    "append:toList:": None,
    "deleteLine:ofList:": None,
    "insert:at:ofList:": None,
    "setLine:ofList:to:": None,
    
    # pen
    "clearPenTrails": None,
    "putPenDown": None,
    "putPenUp": None,
    "penColor:": None,
    "changePenSizeBy:": None,
    "changePenHueBy:": None,
    "setPenHueTo:": None,
    "changePenShadeBy:": None,
    "setPenShadeTo:": None,
    "penSize:": None,
    "stampCostume": None,
    
    # looks
    "lookLike:": None,
    "nextCostume": catbricks.NextLookBrick,
    "startScene": catbricks.SetLookBrick,  # FIXME: wrong / easy: msg broadcast
    "nextScene": catbricks.NextLookBrick,  # FIXME: wrong / easy: msg broadcast
    
    "say:duration:elapsed:from:": None,
    "say:": None,
    "think:duration:elapsed:from:": None,
    "think:": None,
    "changeGraphicEffect:by:": None,  # easy: for ghost, brightness 
    "setGraphicEffect:to:": None,  # easy: for ghost, brightness
    "filterReset": None,  # easy
    "changeSizeBy:": None,  # easy
    "setSizeTo:": None,  # easy
    "show": None,  # easy
    "hide": None,  # easy
    "comeToFront": None,  # easy
    "goBackByLayers:": None,  # easy
    
    # sound
    "playSound:": catbricks.PlaySoundBrick,
    "doPlaySoundAndWait": None,
    "stopAllSounds": None,
    "rest:elapsed:from:": None,
    "noteOn:duration:elapsed:from:": None,
    "setVolumeTo:": None,
    "changeTempoBy:": None,
    "setTempoTo:": None,
    
    # midi
    "playDrum": None,
    
    # sensing
    "doAsk": None,
    "timerReset": None,
    
    ###############################
    # reporter blocks
    ################################
    "+": None,  # easy start
    "-": None,
    "*": None,
    "\/": None,
    "randomFrom:to:": None,
    "<": None,
    "=": None,
    ">": None,
    "&": None,
    "|": None,
    "not": None,  # easy end
    "concatenate:with:": None,
    "letter:of:": None,
    "stringLength:": None,
    "\\\\": None,
    "rounded": None,  # easy
    "computeFunction:of:": None,  # easy
    
    # variables
    "readVariable": None,  # easy
    
    # lists
    "getLine:ofList:": None,
    "lineCountOfList:": None,
    "list:contains:": None,
    
    # sensing
    "touching:": None,
    "touchingColor:": None,
    "color:sees:": None,
    "answer": None,
    "mouseX": None,
    "mouseY": None,
    "mousePressed": None,
    "keyPressed:": None,
    "distanceTo:": None,
    "timer": None,
    "getAttribute:of:": None,
    
    # motion
    "xpos": None,  # easy
    "ypos": None,  # easy
    "heading": None,  # easy
    
    # looks
    "costumeIndex": None,
    "scale": None,  # easy
}


_DEFAULT_BRICK_CLASS = catbricks.WaitBrick


def _get_catrobat_class(sb2name):
    assert isinstance(sb2name, (str, unicode))  
    assert sb2name in SCRATCH_TO_CATROBAT_MAPPING, "Missing mapping for: " + sb2name
    java_class = SCRATCH_TO_CATROBAT_MAPPING.get(sb2name)
    if not java_class:
        if sb2name in sb2.SCRATCH_SCRIPTS:
            assert False, "Missing script mapping for: " + sb2name
        common.log.warning("No mapping for={}, using default class".format(sb2name))
        java_class = lambda *args: _DEFAULT_BRICK_CLASS(args[0], 500)
    return java_class


def _convert_script(sb2script_name, sprite, arguments):
    return _get_catrobat_class(sb2script_name)(sprite, *arguments)


def convert_to_catrobat_project(sb2_project):
    catr_project = catbase.Project(None, sb2_project.name)
    catr_project.getXmlHeader().virtualScreenHeight = sb2.STAGE_HEIGHT_IN_PIXELS
    catr_project.getXmlHeader().virtualScreenWidth = sb2.STAGE_WIDTH_IN_PIXELS
    for _ in sb2_project.project_code.objects:
        catr_sprite = _convert_to_catrobat_sprite(_)
        catr_project.addSprite(catr_sprite)
    return catr_project


def _convert_to_catrobat_sprite(sb2_object):
    if not isinstance(sb2_object, sb2.Object):
        raise common.ScratchtobatError("Input must be of type={}, but is={}".format(sb2.Object, type(sb2_object)))
    sprite = catbase.Sprite(sb2_object.get_objName())
        
    spriteLooks = sprite.getLookDataList()
    for sb2_costume in sb2_object.get_costumes():
        spriteLooks.add(_convert_to_catrobat_look(sb2_costume))
        
    spriteSounds = sprite.getSoundList()
    for sb2_sound in sb2_object.get_sounds():
        spriteSounds.add(_convert_to_catrobat_sound(sb2_sound))
    
    # looks and sounds has to added first because of cross-validations 
    for idx, sb2_script in enumerate(sb2_object.scripts):
        sprite.addScript(_convert_to_catrobat_script(sb2_script, sprite))
    
    # add implicit Scratch behaviour: object's currentCostumeIndex determines active costume at startup
    spriteStartupLookIdx = sb2_object.get_currentCostumeIndex()
    if spriteStartupLookIdx is not None:
        spriteStartupLook = sprite.getLookDataList()[spriteStartupLookIdx]
        set_look_brick = catbricks.SetLookBrick(sprite)
        set_look_brick.setLook(spriteStartupLook)
        
        def get_or_add_startscript(sprite):
            for script in sprite.scriptList:
                if isinstance(script, catbase.StartScript):    
                    return script
            else:
                start_script = catbase.StartScript(sprite)
                sprite.addScript(0, start_script)
                return start_script
        
        start_script = get_or_add_startscript(sprite)
        start_script.addBrick(0, set_look_brick)
        # add implicit Scratch behaviour: object's scratchX and scratchY Keys determines object and therefore costume position
        if sb2_object.get_scratchX() or sb2_object.get_scratchY():
            # sets possible None to 0
            x_pos = sb2_object.get_scratchX() or 0
            y_pos = sb2_object.get_scratchY() or 0
            try:
                place_at_brick = catbricks.PlaceAtBrick(sprite, int(x_pos), int(y_pos))
            except TypeError:
                common.log.warning("Problem with args: {}, {}. Set to default (0, 0)".format(x_pos, y_pos))
                place_at_brick = catbricks.PlaceAtBrick(sprite, 0, 0)
            start_script.addBrick(1, place_at_brick)

    
    return sprite


def _convert_to_catrobat_script(sb2_script, sprite):
    if not isinstance(sb2_script, sb2.Script):
        raise common.ScratchtobatError("Arg1 must be of type={}, but is={}".format(sb2.Script, type(sb2_script)))
    if sprite and not isinstance(sprite, catbase.Sprite):
        raise common.ScratchtobatError("Arg2 must be of type={}, but is={}".format(catbase.Sprite, type(sprite)))

    cat_script = _convert_script(sb2_script.type, sprite, sb2_script.arguments)
    for sb2_brick in sb2_script.bricks:
        cat_bricks = _convert_to_catrobat_bricks(sb2_brick, sprite)
        for brick in cat_bricks:
            cat_script.addBrick(brick)
    return cat_script


def _convert_to_catrobat_bricks(sb2_brick, cat_sprite):
    common.log.debug("Brick to convert={}".format(sb2_brick))
    if not sb2_brick or not (isinstance(sb2_brick, list) and isinstance(sb2_brick[0], (str, unicode))):
        raise common.ScratchtobatError("Wrong arg1, must be list with string as first element: {!r}".format(sb2_brick))
    if not isinstance(cat_sprite, catbase.Sprite):
        raise common.ScratchtobatError("Wrong arg2, must be of type={}, but is={}".format(catbase.Sprite, type(cat_sprite)))
    if not sb2_brick[0] in SCRATCH_TO_CATROBAT_MAPPING:
        raise common.ScratchtobatError("Unknown brick identifier: {}".format(sb2_brick))
    brick_name = sb2_brick[0]
    brick_arguments = sb2_brick[1:]
    catr_bricks = []
    try:
        # Bricks which special handling because of e.g. argument mismatch 
        if brick_name in {'doRepeat', 'doForever'}:
            if brick_name == 'doRepeat':
                times_value, nested_bricks = brick_arguments
                if isinstance(times_value, list):
                    common.log.warning("Unsupported times_value: {}. Set to default (1).".format(times_value))
                    times_value = 1
                catr_loop_start_brick = _get_catrobat_class(brick_name)(cat_sprite, times_value)
            elif brick_name == 'doForever':
                [nested_bricks] = brick_arguments
                catr_loop_start_brick = _get_catrobat_class(brick_name)(cat_sprite)
            else:
                assert False, "Missing conditional branch for: " + brick_name
            catr_bricks += [catr_loop_start_brick]
            for brick_arg in nested_bricks:
                catr_bricks += _convert_to_catrobat_bricks(brick_arg, cat_sprite)
            catr_bricks += [catbricks.LoopEndBrick(cat_sprite, catr_loop_start_brick)]
            
        elif brick_name == "playSound:":
            [look_name] = brick_arguments
            soundinfo_name_to_soundinfo_map = {lookdata.getTitle(): lookdata for lookdata in cat_sprite.getSoundList()}
            lookdata = soundinfo_name_to_soundinfo_map.get(look_name)
            if not lookdata:
                raise ConversionError("Sprite does not contain sound with name={}".format(look_name))
            play_sound_brick = _get_catrobat_class(brick_name)(cat_sprite)
            play_sound_brick.setSoundInfo(lookdata)
            catr_bricks += [play_sound_brick]

        # same structure as 'playSound' above
        elif brick_name == "startScene":
            [look_name] = brick_arguments
            matching_lookdatas = [_ for _ in cat_sprite.getLookDataList() if _.getLookName() == look_name]
            if not matching_lookdatas:
                raise ConversionError("Sprite does not contain look with name={}".format(look_name))
            assert len(matching_lookdatas) == 1
            [lookdata] = matching_lookdatas
            set_look_brick = _get_catrobat_class(brick_name)(cat_sprite)
            set_look_brick.setLook(lookdata)
            catr_bricks += [set_look_brick]
             
        else:
            common.log.debug("Get mapping for {} in {}".format(brick_name, cat_sprite))
            catr_bricks += [_get_catrobat_class(brick_name)(cat_sprite, *brick_arguments)]
    except TypeError as e:
        common.log.exception(e)
        assert False, "Non-matching arguments: {}".format(brick_arguments)
    return catr_bricks


def _convert_to_catrobat_look(costume):
    if not costume or not (isinstance(costume, dict) and all(_ in costume for _ in (sb2keys.BASELAYERMD5_KEY, sb2keys.COSTUMENAME_KEY))):
        raise common.ScratchtobatError("Wrong input, must be costume dict: {}".format(costume))
    look = catcommon.LookData()
    
    assert sb2keys.COSTUMENAME_KEY  in costume
    costume_name = costume[sb2keys.COSTUMENAME_KEY]
    look.setLookName(costume_name)
    
    assert sb2keys.BASELAYERMD5_KEY in costume
    costume_filename = costume[sb2keys.BASELAYERMD5_KEY]
    costume_filename_ext = os.path.splitext(costume_filename)[1]
    look.setLookFilename(costume_filename.replace(costume_filename_ext, "_" + costume_name + costume_filename_ext))
    return look


def _convert_to_catrobat_sound(sound):
    soundinfo = catcommon.SoundInfo()
    
    assert sb2keys.SOUNDNAME_KEY in sound
    sound_name = sound[sb2keys.SOUNDNAME_KEY]
    soundinfo.setTitle(sound_name) 
    
    assert sb2keys.MD5_KEY in sound
    sound_filename = sound[sb2keys.MD5_KEY]
    sound_filename_ext = os.path.splitext(sound_filename)[1]
    soundinfo.setSoundFileName(sound_filename.replace(sound_filename_ext, "_" + sound_name + sound_filename_ext)) 
    return soundinfo


class ConversionError(common.ScratchtobatError):
        pass


def convert_sb2_project_to_catroid_zip(project, catroid_zip_file_path):
    temp_dir = tempfile.mkdtemp()
    convert_sb2_project_to_catroid_project_structure(project, temp_dir)

    def iter_dir(path):
        for root, dirs, files in os.walk(path):
            for file in files:
                yield os.path.join(root, file)

    with zipfile.ZipFile(catroid_zip_file_path, 'w') as zip_fp:
        for file_path in iter_dir(temp_dir):
            zip_fp.write(file_path, file_path.replace(temp_dir, project.name))
            
    shutil.rmtree(temp_dir)


def images_path_of_project(temp_dir):
    return os.path.join(temp_dir, "images")


def sounds_path_of_project(temp_dir):
    return os.path.join(temp_dir, "sounds")


def convert_sb2_project_to_catroid_project_structure(project, temp_path):
    sounds_path = sounds_path_of_project(temp_path)
    os.mkdir(sounds_path)
    
    images_path = images_path_of_project(temp_path)
    os.mkdir(images_path)
    
    for _ in (temp_path, sounds_path, images_path):
        open(os.path.join(_, CATROID_NOMEDIA_FILE), 'a').close()
    
    for md5_name in project.md5_to_resource_path_map:
        src_path = project.md5_to_resource_path_map[md5_name]
        file_ext = os.path.splitext(md5_name)[1]
        converted_file = False
        
        if file_ext in {".png", ".svg"}:
            target_dir = images_path
            if file_ext == ".svg":
                # TODO: refactor
                resource = project.project_code.resource_dict_of_md5_name(md5_name)
                assert resource, md5_name
                png_path = svgtopng.convert(src_path)
                with open(png_path, "rb") as fp:
                    md5_hash = hashlib.md5(fp.read()).hexdigest()
                assert sb2keys.BASELAYERMD5_KEY in resource, resource
                md5_name = resource[sb2keys.BASELAYERMD5_KEY] = md5_hash + ".png"
                src_path = png_path
                converted_file = True
        elif file_ext in {".wav"}:
            target_dir = sounds_path
        else:
            assert file_ext in {".json"}, md5_name
            continue
        
        catroid_file_name = catroid_resource_name_of_sb2_resource(project, md5_name)
        # WORKAROUND: for  "penLayerMD5": "279467d0d49e152706ed66539b577c00.png",
        if not catroid_file_name:
            continue
        shutil.copyfile(src_path, os.path.join(target_dir, catroid_file_name))
        if converted_file:
            os.remove(src_path)

    catroid_project = convert_to_catrobat_project(project)
    storage_handler = catio.StorageHandler().getInstance()
    code_xml_content = storage_handler.XML_HEADER
    code_xml_content += storage_handler.getXMLStringOfAProject(catroid_project)

    with open(os.path.join(temp_path, CATROID_PROJECT_FILE), "wb") as fp:
        fp.write(code_xml_content)


def catroid_resource_name_of_sb2_resource(project, md5_name):
    resource = project.project_code.resource_dict_of_md5_name(md5_name)
    if not resource:
        return None
    try:
        resource_name = resource[sb2keys.SOUNDNAME_KEY] if sb2keys.SOUNDNAME_KEY in resource else resource[sb2keys.COSTUMENAME_KEY]
    except KeyError:
        raise ConversionError("Error with: {}, {}".format(md5_name, resource))
    resource_ext = os.path.splitext(md5_name)[1]
    catroid_resource_name = md5_name.replace(resource_ext, "_" + resource_name + resource_ext)
    return catroid_resource_name


def _keyPressedToBroadcastMessage(keyName):
    return "key" + keyName + "Pressed"


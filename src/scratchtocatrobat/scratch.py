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
import copy
import glob
import itertools
import json
import os
import zipfile

from scratchtocatrobat import common
from scratchtocatrobat import scratchwebapi

log = common.log

HTTP_PROJECT_URL_PREFIX = "http://scratch.mit.edu/projects/"

SCRIPT_GREEN_FLAG, SCRIPT_RECEIVE, SCRIPT_KEY_PRESSED, SCRIPT_SENSOR_GREATER_THAN, SCRIPT_SCENE_STARTS, SCRIPT_CLICKED = SCRATCH_SCRIPTS = \
    ["whenGreenFlag", "whenIReceive", "whenKeyPressed", "whenSensorGreaterThan", "whenSceneStarts", "whenClicked", ]
SCRATCH_PROJECT_CODE_FILE = "project.json"
STAGE_OBJECT_NAME = "Stage"
STAGE_HEIGHT_IN_PIXELS = 360
STAGE_WIDTH_IN_PIXELS = 480


class JsonKeys(object):
    # TODO: remove '_KEY' suffix
    BASELAYER_ID = "baseLayerID"
    CHILDREN = "children"
    COSTUME_MD5 = "baseLayerMD5"
    COSTUME_RESOLUTION = "bitmapResolution"
    COSTUME_NAME = "costumeName"
    COSTUMES = "costumes"
    INFO = "info"
    PROJECT_ID = 'projectID'
    OBJECT_NAME = "objName"
    SCRIPTS = "scripts"
    SOUND_MD5 = "md5"
    SOUND_ID = "soundID"
    SOUND_NAME = "soundName"
    SOUNDS = "sounds"
    VARIABLES = 'variables'


def extract_project(input_scratch, output_path):
    with zipfile.ZipFile(input_scratch, 'r') as myzip:
        myzip.extractall(output_path)


class RawProject(common.DictAccessWrapper):
    """
    Represents the raw Scratch project structure.
    """

    def __init__(self, dict_, data_origin="<undefined>"):
        super(RawProject, self).__init__(dict_)
        self._verify_scratch_dictionary(dict_, data_origin)
        self.raw_objects = [child for child in self.get_children() if "objName" in child]
        self.objects = [Object(raw_object) for raw_object in [self._raw_stage_object_without_project_variables(dict_)] + self.raw_objects]
        self.stage_object = self.objects[0]
        assert self.stage_object.get_info() is not None
        self.nonstage_objects = self.objects[1:]
        self.resource_names = {self._resource_name_from(raw_resource) for raw_resource in self._raw_resources()}

    def _verify_scratch_dictionary(self, dict_, data_origin):
        # FIXME: check which tags are really required
        for key in ["objName", "info", "currentCostumeIndex", "penLayerMD5", "tempoBPM", "videoAlpha", "children", "costumes", "sounds"]:
            if key not in dict_:
                raise UnsupportedProjectFileError("In project file from: '{}' key='{}' must be set.".format(data_origin, key))

    def _raw_stage_object_without_project_variables(self, dict_):
        raw_stage_object = copy.deepcopy(dict_)
        # Variables defined on the stage object are in fact project variables, so removing them here.
        raw_stage_object["variables"] = []
        return raw_stage_object

    def _raw_resources(self):
        return itertools.chain.from_iterable(object_.get_sounds() + object_.get_costumes() for object_ in self.objects)

    def _resource_name_from(self, raw_resource):
        assert JsonKeys.SOUND_MD5 in raw_resource or JsonKeys.COSTUME_MD5 in raw_resource
        md5_file_name = raw_resource[JsonKeys.SOUND_MD5] if JsonKeys.SOUND_NAME in raw_resource else raw_resource[JsonKeys.COSTUME_MD5]
        return md5_file_name

    @staticmethod
    def raw_project_code_from_project_folder_path(project_folder_path):
        dict_path = os.path.join(project_folder_path, SCRATCH_PROJECT_CODE_FILE)
        if not os.path.exists(dict_path):
            raise EnvironmentError("Project file not found: {!r}. Please create.".format(dict_path))
        with open(dict_path) as fp:
            return json.load(fp)

    @classmethod
    def from_project_folder_path(cls, project_folder_path):
        return cls(cls.raw_project_code_from_project_folder_path(project_folder_path))

    @classmethod
    def from_project_code_content(cls, code_content):
        return cls(json.loads(code_content))


class Project(RawProject):
    """
    Represents a complete Scratch project including all resource files.
    """

    def __init__(self, project_base_path, name=None, id_=None):
        def read_md5_to_resource_path_mapping():
            md5_to_resource_path_map = {}
            for project_file_path in glob.glob(os.path.join(project_base_path, "*")):
                resource_name = common.md5_hash(project_file_path) + os.path.splitext(project_file_path)[1]
                md5_to_resource_path_map[resource_name] = project_file_path
            try:
                # penLayer is no regular resource file
                del md5_to_resource_path_map[self['penLayerMD5']]
            except KeyError:
                # TODO: include penLayer download in webapi
                pass
            return md5_to_resource_path_map

        def verify_resources(resources):
            for res_dict in resources:
                assert JsonKeys.SOUND_MD5 in res_dict or JsonKeys.COSTUME_MD5 in res_dict
                md5_file = res_dict[JsonKeys.SOUND_MD5] if JsonKeys.SOUND_NAME in res_dict else res_dict[JsonKeys.COSTUME_MD5]
                resource_md5 = os.path.splitext(md5_file)[0]
                if md5_file not in self.md5_to_resource_path_map:
                    raise ProjectError("Missing resource file at project: {}. Provide resource with md5: {}".format(project_base_path, resource_md5))

        super(Project, self).__init__(self.raw_project_code_from_project_folder_path(project_base_path))
        self.project_base_path = project_base_path
        if id_ is not None:
            self.project_id = id_
        else:
            self.project_id = self.get_info().get("projectID")
        if not self.project_id:
            raise ProjectError("No project id specified in project file. Please provide project id with constructor.")
        if name is not None:
            self.name = name
            self.description = ""
        else:
            self.name = scratchwebapi.request_project_name_for(self.project_id)
            self.description = scratchwebapi.request_project_description_for(self.project_id)
        # TODO: move whole block including the two functions to ProjectCode
        self.md5_to_resource_path_map = read_md5_to_resource_path_mapping()
        assert self['penLayerMD5'] not in self.md5_to_resource_path_map
        for scratch_object in self.objects:
            # TODO: rename to verify_object?
            verify_resources(scratch_object.get_sounds() + scratch_object.get_costumes())

        listened_keys = []
        for object_ in self.objects:
            for script in object_.scripts:
                if script.type == SCRIPT_KEY_PRESSED:
                    assert len(script.arguments) == 1
                    listened_keys += script.arguments
        self.listened_keys = set(listened_keys)
        # TODO: rename
        self.background_md5_names = set([costume[JsonKeys.COSTUME_MD5] for costume in self.stage_object.get_costumes()])
        self.unused_resource_names, self.unused_resource_paths = common.pad(zip(*self.find_unused_resources_name_and_filepath()), 2, [])
        for unused_path in self.unused_resource_paths:
            log.warning("Project folder contains unused resource file: '%s'. These will be omitted for Catrobat project.", os.path.basename(unused_path))

    def find_unused_resources_name_and_filepath(self):
        for file_path in glob.glob(os.path.join(self.project_base_path, "*")):
            md5_resource_filename = common.md5_hash(file_path) + os.path.splitext(file_path)[1]
            if md5_resource_filename not in self.resource_names:
                if os.path.basename(file_path) != SCRATCH_PROJECT_CODE_FILE:
                    yield md5_resource_filename, file_path

    def find_all_resource_dicts_for(self, resource_name):
        for resource in self._raw_resources():
            if resource_name in set([resource.get(JsonKeys.SOUND_MD5), resource.get(JsonKeys.COSTUME_MD5)]):
                yield resource


# TODO: rename
# TODO: do not use DictAccessWrapper
class Object(common.DictAccessWrapper):

    def __init__(self, object_data):
        if not self.is_valid_class_input(object_data):
            raise ObjectError("Input is no valid Scratch object.")
        for key in (JsonKeys.SOUNDS, JsonKeys.COSTUMES, JsonKeys.SCRIPTS, JsonKeys.VARIABLES):
            if key not in object_data:
                object_data[key] = []
        super(Object, self).__init__(object_data)
        self.scripts = [Script(_) for _ in self.get_scripts() if Script.is_valid_script_input(_)]

    @classmethod
    def is_valid_class_input(cls, object_data):
        return 'objName' in object_data


# TODO: rename
class Script(object):

    def __init__(self, json_input):
        if not self.is_valid_script_input(json_input):
            raise ScriptError("Input is no valid Scratch json script.")
        self.raw_script = json_input[2]
        script_block, self.blocks = self.raw_script[0], self.raw_script[1:]
        self.type, self.arguments = script_block[0], script_block[1:]
        if self.type not in SCRATCH_SCRIPTS:
            raise ScriptError("Unknown Scratch script type: {}".format(self.type))

    @classmethod
    def is_valid_script_input(cls, json_input):
        if (isinstance(json_input, list) and len(json_input) == 3 and isinstance(json_input[0], int) and isinstance(json_input[1], int) and isinstance(json_input[2], list)):
            # NOTE: could use a json validator instead
            script_content = json_input[2]
            if script_content[0][0] in SCRATCH_SCRIPTS:
                return True

        log.warning("No valid Scratch script: {}".format(json_input))
        return False

    def get_type(self):
        return self.type


class UnsupportedProjectFileError(common.ScratchtobatError):
    pass


class ProjectCodeError(common.ScratchtobatError):
    pass


class ProjectError(common.ScratchtobatError):
    pass


class ObjectError(common.ScratchtobatError):
    pass


class ScriptError(common.ScratchtobatError):
    pass

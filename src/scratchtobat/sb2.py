# based on: http://code.google.com/p/sb2-js/source/browse/trunk/editor.htm
from scratchtobat import common
import os
import json


class Project(object):
    _SCRATCH_PROJECT_DATA_FILE = "project.json"
    
    def __init__(self, project_path):
        if not os.path.isdir(project_path):
            raise ProjectError("Create project path: {}".format(project_path))
        self.json_path = os.path.join(project_path, self._SCRATCH_PROJECT_DATA_FILE)
        self.project_data = self.load_json_file(self.json_path)
        # TODO: property
        self.stage_data = None
        self.objects_data = [_ for _ in self.project_data["children"] if "objName" in _]
        
    def load_json_file(self, json_file):
        if not os.path.exists(json_file):
            raise ProjectError("Provide project data file: {}".format(json_file))
        with open(json_file, "r") as fp:
            json_dict = json.load(fp)
            self.verify_scratch_json(json_dict)
            return json_dict
        
    def get_raw_data(self):
        return self.project_data
    
    def verify_scratch_json(self, json_dict):
        # FIXME: check which tags are really required
        for key in ["objName", "info", "currentCostumeIndex", "penLayerMD5", "tempoBPM", "videoAlpha", "children", "costumes", "sounds"]:
            if not key in json_dict:
                raise ProjectError("Key='{}' not found in {}".format(key, self.json_path))


class ProjectError(common.ScratchtobatError):
    pass


class Object(object):
    
    def __init__(self, object_data):
        if not self.is_valid_class_input(object_data):
            raise ObjectError("Input is no valid Scratch json sb2 object.")        
    
    @classmethod
    def is_valid_class_input(cls, json_input):
        return 'objName' in json_input


class ObjectError(common.ScratchtobatError):
    pass


class Script(object):
    
    def __init__(self, json_input):
        if not self.is_valid_script_input(json_input):
            raise ScriptError("Input is no valid Scratch sb2 json script.")
        script_content = json_input[2]
        self.script_id = script_content[0]
        self.script_bricks = script_content[1:]

    @classmethod
    def is_valid_script_input(cls, json_input):
        return (isinstance(json_input, list) and len(json_input) == 3 and
            # NOTE: could use a json validator instead
            isinstance(json_input[0], int) and isinstance(json_input[1], int) and isinstance(json_input[2], list))
    
    def get_type(self):
        return self.script_id[0]
        
    def get_raw_bricks(self):
        def get_bricks_recursively(nested_bricks):
            result = []
            common.log.info("{}".format(nested_bricks))
            for idx, brick in enumerate(nested_bricks):
                isBrickId = idx == 0 and isinstance(brick, str)
                isNestedBrick = isinstance(brick, list)
                if isBrickId:
                    common.log.debug("adding {}".format(brick))
                    result += [brick]
                elif isNestedBrick:
                    common.log.debug("calling on {}".format(brick))
                    result += get_bricks_recursively(brick)
                else:
                    assert isinstance(brick, (int, str, float)), "Unhandled brick element type {} for {}".format(type(brick), brick)
                    continue
            return result
        
        return get_bricks_recursively(self.script_bricks)


class ScriptError(common.ScratchtobatError):
    pass

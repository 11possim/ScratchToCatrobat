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
import hashlib
import json
import os
import re
import urllib2
from urlparse import urlparse
from scratchtocatrobat import common
from tools import helpers

_log = common.log

class ProjectInfoKeys(object):
    PROJECT_DESCRIPTION = 'description'
    PROJECT_NAME = 'title'

def request_project_code(project_id):
    def project_json_request_url(project_id):
        return helpers.config.get("SCRATCH_API", "project_url_template").format(project_id)

    try:
        request_url = project_json_request_url(project_id)
        return common.url_response_data(request_url)
#     except urllib2.HTTPError as e:
    except None as e:
        raise common.ScratchtobatError("Error with {}: '{}'".format(request_url, e))

def is_valid_project_url(project_url):
    scratch_base_url = helpers.config.get("SCRATCH_API", "project_base_url")
    _HTTP_PROJECT_URL_PATTERN = scratch_base_url + r'\d+/?'
    return re.match(_HTTP_PROJECT_URL_PATTERN, project_url)

def download_project(project_url, target_dir):
    import scratch
    # TODO: fix circular reference
    scratch_base_url = helpers.config.get("SCRATCH_API", "project_base_url")
    if not is_valid_project_url(project_url):
        raise common.ScratchtobatError("Project URL must be matching '{}'. Given: {}".format(scratch_base_url + '<project id>', project_url))
    assert len(os.listdir(target_dir)) == 0

    def request_resource_data(md5_file_name):
        request_url = project_resource_request_url(md5_file_name)
        try:
            response_data = common.url_response_data(request_url)
            # FIXME: fails for some projects...
            verify_hash = hashlib.md5(response_data).hexdigest()
            assert verify_hash == os.path.splitext(md5_file_name)[0], "MD5 hash of response data not matching"
            return response_data
        except urllib2.HTTPError as e:
            raise common.ScratchtobatError("Error with {}: '{}'".format(request_url, e))

    def project_resource_request_url(md5_file_name):
        return helpers.config.get("SCRATCH_API", "asset_url_template").format(md5_file_name)

    def project_id_from_url(project_url):
        normalized_url = project_url.strip("/")
        project_id = os.path.basename(urlparse(normalized_url).path)
        return project_id

    def write_to(data, file_path):
        with open(file_path, "wb") as fp:
            fp.write(data)

    def project_code_path(target_dir):
        return os.path.join(target_dir, scratch._PROJECT_FILE_NAME)

    # TODO: consolidate with classes from scratch module
    project_id = project_id_from_url(project_url)
    project_file_path = project_code_path(target_dir)
    write_to(request_project_code(project_id), project_file_path)

    project = scratch.RawProject.from_project_folder_path(target_dir)
    for md5_file_name in project.resource_names:
        resource_file_path = os.path.join(target_dir, md5_file_name)
        write_to(request_resource_data(md5_file_name), resource_file_path)

def _project_info_request_url(project_id):
    return helpers.config.get("SCRATCH_API", "project_info_url_template").format(project_id)

def _request_project_info(project_id):
    # TODO: cache this request...
    response_data = common.url_response_data(_project_info_request_url(project_id))
    return json.loads(response_data)

# TODO: class instead of request functions
def request_project_name_for(project_id):
    return _request_project_info(project_id)[ProjectInfoKeys.PROJECT_NAME]

def request_project_description_for(project_id):
    scratch_base_url = helpers.config.get("SCRATCH_API", "project_base_url")
    scratch_project_url = scratch_base_url + str(project_id)
    if not is_valid_project_url(scratch_project_url):
        raise common.ScratchtobatError("Project URL must be matching '{}'. Given: {}".format(scratch_base_url + '<project id>', scratch_project_url))

    from org.jsoup import Jsoup
    doc = Jsoup.connect(scratch_project_url).get()
    element = doc.select("div#instructions > div.viewport > div.overview").first()
    description = ""
    if element is not None:
        description += element.text().strip()

    ######################################################################################
    # TODO: do the same in order to parse the "Notes and Credits"
    #       and append the parsed string to the description string
    #-------------------------------------------------------------------------------------
    # ... Code goes here ...
    description += "" # TODO: append "Notes and Credits" string instead of empty string
    ######################################################################################
    return description # finally return the description

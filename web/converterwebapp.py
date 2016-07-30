#  ScratchToCatrobat: A tool for converting Scratch projects into Catrobat programs.
#  Copyright (C) 2013-2015 The Catrobat Team
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
#
#  ---------------------------------------------------------------------------------------
#  NOTE:
#  ---------------------------------------------------------------------------------------
#  This module is a simple web socket server based on the Tornado web framework and
#  asynchronous networking library, which is licensed under the Apache License, Version 2.0.
#  For more information about the Apache License please visit:
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  For scheduling purposes the rq library (based on Redis) is used.
#  The rq library is licensed under the BSD License:
#
#    https://raw.github.com/nvie/rq/master/LICENSE
#

"""
  Simple web socket server for handling conversion requests.
"""

import logging
import tornado.escape #@UnresolvedImport
import tornado.web #@UnresolvedImport
import tornado.websocket #@UnresolvedImport
from tornado import httputil, httpclient #@UnresolvedImport
from bs4 import BeautifulSoup #@UnresolvedImport
import os.path
import redis #@UnresolvedImport
from command import get_command, InvalidCommand, Job, update_jobs_info_on_listening_clients
import jobmonitorprotocol as jobmonprot
from tornado.web import HTTPError #@UnresolvedImport
import ast, sys
from datetime import datetime as dt, timedelta
import converterwebsocketprotocol as protocol
from jobmonitorprotocol import NotificationType
from scratchtocatrobat import scratchwebapi
from scratchtocatrobat.scratchwebapi import ScratchProjectVisibiltyState
import urllib

sys.path.append(os.path.join(os.path.realpath(os.path.dirname(__file__)), "..", "src"))
from scratchtocatrobat.tools import helpers

_logger = logging.getLogger(__name__)

CATROBAT_FILE_EXT = helpers.config.get("CATROBAT", "file_extension")
CONVERTER_API_SETTINGS = helpers.config.items_as_dict("CONVERTER_API")
SCRATCH_PROJECT_BASE_URL = helpers.config.get("SCRATCH_API", "http_delay")
HTTP_RETRIES = int(helpers.config.get("SCRATCH_API", "http_retries"))
HTTP_BACKOFF = int(helpers.config.get("SCRATCH_API", "http_backoff"))
HTTP_DELAY = int(helpers.config.get("SCRATCH_API", "http_delay"))
HTTP_TIMEOUT = int(helpers.config.get("SCRATCH_API", "http_timeout"))
HTTP_USER_AGENT = helpers.config.get("SCRATCH_API", "user_agent")
SCRATCH_PROJECT_BASE_URL = helpers.config.get("SCRATCH_API", "project_base_url")

# TODO: check if redis is available => error!
_redis_conn = redis.Redis() #'127.0.0.1', 6789) #, password='secret')


class Context(object):
    def __init__(self, handler, redis_connection, jobmonitorserver_settings):
        self.handler = handler
        self.redis_connection = redis_connection
        self.jobmonitorserver_settings = jobmonitorserver_settings

class ConverterWebSocketHandler(tornado.websocket.WebSocketHandler):

    client_ID_open_sockets_map = {}

    def get_compression_options(self):
        return {} # Non-None enables compression with default options.

    def set_client_ID(self, client_ID):
        cls = self.__class__
        if client_ID not in cls.client_ID_open_sockets_map:
            cls.client_ID_open_sockets_map[client_ID] = []
        cls.client_ID_open_sockets_map[client_ID].append(self)

    @classmethod
    def notify(cls, msg_type, args):
        # Note: jobID is always equivalent to scratch project ID
        job_ID = args[jobmonprot.Request.ARGS_JOB_ID]
        REDIS_CLIENT_PROJECT_KEY = "clientsOfProject#{}".format(job_ID)
        REDIS_PROJECT_KEY = "project#{}".format(job_ID)
        job = Job.from_redis(_redis_conn, REDIS_PROJECT_KEY)
        old_status = job.status
        if job == None:
            _logger.error("Cannot find job #{}".format(job_ID))
            return
        if msg_type == NotificationType.JOB_STARTED:
            job.title = args[jobmonprot.Request.ARGS_TITLE]
            job.status = Job.Status.RUNNING
        elif msg_type == NotificationType.JOB_FAILED:
            _logger.warn("Job failed! Exception Args: %s", args)
            job.status = Job.Status.FAILED
        elif msg_type == NotificationType.JOB_OUTPUT:
            if job.output == None: job.output = ""
            for line in args[jobmonprot.Request.ARGS_LINES]:
                job.output += line
        elif msg_type == NotificationType.JOB_PROGRESS:
            job.progress = args[jobmonprot.Request.ARGS_PROGRESS]
        elif msg_type == NotificationType.JOB_FINISHED:
            _logger.info("Job #{} finished, waiting for file transfer".format(job_ID))
        elif msg_type == NotificationType.FILE_TRANSFER_FINISHED:
            job.progress = 100.0
            job.status = Job.Status.FINISHED
            job.archive_cached_date = dt.now().strftime(Job.DATETIME_FORMAT)
        if not job.save_to_redis(_redis_conn, REDIS_PROJECT_KEY):
            _logger.info("Unable to update job status!")
            return

        # inform all clients if status or progress changed
        if old_status != job.status or msg_type == NotificationType.JOB_PROGRESS:
            update_jobs_info_on_listening_clients(Context(None, _redis_conn, None))

        # find listening clients
        # TODO: cache this...
        clients_of_project = _redis_conn.get(REDIS_CLIENT_PROJECT_KEY)
        if clients_of_project == None:
            _logger.warn("WTH?! No listening clients stored!")
            return

        clients_of_project = ast.literal_eval(clients_of_project)
        num_clients_of_project = len(clients_of_project)
        _logger.debug("There %s %d registered client%s." % \
                      ("is" if num_clients_of_project == 1 else "are", \
                       num_clients_of_project, "s" if num_clients_of_project != 1 else ""))
        listening_clients = [cls.client_ID_open_sockets_map[int(client_ID)] for client_ID in clients_of_project if int(client_ID) in cls.client_ID_open_sockets_map]
        _logger.debug("There are %d active clients listening on this job." % len(listening_clients))

        for socket_handlers in listening_clients:
            if msg_type == NotificationType.JOB_STARTED:
                message = protocol.JobRunningMessage(job_ID)
            elif msg_type == NotificationType.JOB_OUTPUT:
                message = protocol.JobOutputMessage(job_ID, args[jobmonprot.Request.ARGS_LINES])
            elif msg_type == NotificationType.JOB_PROGRESS:
                message = protocol.JobProgressMessage(job_ID, args[jobmonprot.Request.ARGS_PROGRESS])
            elif msg_type == NotificationType.JOB_FINISHED:
                message = protocol.JobFinishedMessage(job_ID)
            elif msg_type == NotificationType.FILE_TRANSFER_FINISHED:
                download_url = "/download?id=" + str(job_ID) + "&fname=" + urllib.quote_plus(job.title)
                message = protocol.JobDownloadMessage(job_ID, download_url, job.archive_cached_date)
            elif msg_type == NotificationType.JOB_FAILED:
                message = protocol.JobFailedMessage(job_ID)
            else:
                _logger.warn("IGNORING UNKNOWN MESSAGE")
                return
            for handler in socket_handlers:
                handler.send_message(message)

    def on_close(self):
        cls = self.__class__
        _logger.info("Closing websocket")
        for (client_ID, open_sockets) in cls.client_ID_open_sockets_map.iteritems():
            if self in open_sockets:
                open_sockets.remove(self)
                if len(open_sockets) == 0:
                    del cls.client_ID_open_sockets_map[client_ID]
                else:
                    cls.client_ID_open_sockets_map[client_ID] = open_sockets
                _logger.info("Found websocket and closed it")
                return # break out of loop => limit is 1 socket/clientID

    def send_message(self, message):
        assert isinstance(message, protocol.Message)
        _logger.debug("Sending %s %r to %d", message.__class__.__name__,
                      message.as_dict(), id(self))
        try:
            self.write_message(tornado.escape.json_encode(message.as_dict()))
        except:
            _logger.error("Error sending message", exc_info=True)

    def on_message(self, message):
        _logger.debug("Received message %r", message)
        data = tornado.escape.json_decode(message)
        args = {}
        if protocol.JsonKeys.Request.is_valid(data):
            command = get_command(data[protocol.JsonKeys.Request.CMD])
            args = protocol.JsonKeys.Request.extract_allowed_args(data[protocol.JsonKeys.Request.ARGS])
        else:
            command = InvalidCommand()
        # TODO: when client ID is given => check if it belongs to socket handler!
        redis_conn = _redis_conn
        ctxt = Context(self, redis_conn, self.application.settings["jobmonitorserver"])
        _logger.info("Executing command %s", command.__class__.__name__)
        self.send_message(command.execute(ctxt, args))

class _MainHandler(tornado.web.RequestHandler):
    app_data = {}
    def get(self):
        self.render("index.html", data=_MainHandler.app_data)

class _DownloadHandler(tornado.web.RequestHandler):
    def get(self):
        # TODO: support head request!
        scratch_project_id_string = self.get_query_argument("id", default=None)
        if scratch_project_id_string == None or not scratch_project_id_string.isdigit():
            raise HTTPError(404)
        file_dir = self.application.settings["jobmonitorserver"]["download_dir"]
        file_name = scratch_project_id_string + CATROBAT_FILE_EXT
        file_path = "%s/%s" % (file_dir, file_name)
        if not file_name or not os.path.exists(file_path):
            raise HTTPError(404)
        file_size = os.path.getsize(file_path)
        self.set_header('Content-Type', 'application/zip')
        self.set_header('Content-Disposition', 'attachment; filename="%s"' % file_name)
        with open(file_path, "rb") as f:
            range_header = self.request.headers.get("Range")
            request_range = None
            if range_header:
                # TODO: implement own parse request range helper method
                request_range = httputil._parse_request_range(range_header, file_size)

            if request_range:
                # TODO: support HTTP range + test
                # TODO: request_range.end
                self.set_header('Content-Range', 'bytes {}-{}/{}'.format(request_range.start, (file_size - 1), file_size))
                self.set_header('Content-Length', file_size - request_range.start + 1)#(request_range.end - request_range.start + 1))
                file.seek(request_range.start)
            else:
                self.set_header('Content-Length', file_size)

            try:
                while True:
                    write_buffer = f.read(4096) # XXX: what if file is smaller than this buffer-size?
                    if write_buffer:
                        self.write(write_buffer)
                    else:
                        self.finish()
                        return
            except:
                raise HTTPError(404)
        raise HTTPError(500)

class _ResponseBeautifulSoupDocumentWrapper(scratchwebapi.ResponseDocumentWrapper):
    def select_first_as_text(self, query):
        result = self.wrapped_document.select(query)
        if result is None or not isinstance(result, list) or len(result) == 0:
            return None
        return result[0].get_text()

    def select_all_as_text_list(self, query):
        result = self.wrapped_document.select(query)
        if result is None:
            return None
        return [element.get_text() for element in result if element is not None]

    def select_attributes_as_text_list(self, query, attribute_name):
        result = self.wrapped_document.select(query)
        if result is None:
            return None
        return [element[attribute_name] for element in result if element is not None]


class ProjectDataResponse(object):

    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self):
        self.accessible = True
        self.visibility_state = ScratchProjectVisibiltyState.UNKNOWN
        self.project_data = {}
        self.valid_until = None

    def as_dict(self):
        cls = self.__class__
        return {
            "accessible": self.accessible,
            "visibility": self.visibility_state,
            "projectData": self.project_data,
            "validUntil": None if not self.valid_until else self.valid_until.strftime(cls.DATETIME_FORMAT)
        }


class _ProjectHandler(tornado.web.RequestHandler):
    response_cache = {}
    CACHE_ENTRY_VALID_FOR = 600 # 10 minutes (in seconds)

    @tornado.gen.coroutine
    def get(self, project_id = None):
        # ------------------------------------------------------------------------------------------
        # Featured projects HTTP-request
        # ------------------------------------------------------------------------------------------
        if project_id is None:
            # TODO: automatically update featured projects...
            self.write({ "results": CONVERTER_API_SETTINGS["featured_projects"] })
            return

        # ------------------------------------------------------------------------------------------
        # Project details HTTP-request
        # ------------------------------------------------------------------------------------------
        cls = self.__class__
        if project_id in cls.response_cache and dt.now() <= cls.response_cache[project_id].valid_until:
            _logger.info("Cache hit for project ID {}".format(project_id))
            self.write(cls.response_cache[project_id].as_dict())
            return

        try:
            scratch_project_url = SCRATCH_PROJECT_BASE_URL + str(project_id)
            _logger.info("Fetching project info from: {}".format(scratch_project_url))
            http_response = yield self.application.async_http_client.fetch(scratch_project_url)
        except tornado.httpclient.HTTPError, e:
            _logger.warn("Unable to download project's web page: HTTP-Status-Code: " + str(e.code))
            response = ProjectDataResponse()
            if e.code == 404:
                # 'HTTP 404 - Not found' means not accessible
                # (e.g. projects that have been removed in the meanwhile...)
                response.accessible = False
                response.valid_until = dt.now() + timedelta(seconds=cls.CACHE_ENTRY_VALID_FOR)
                cls.response_cache[project_id] = response

            self.write(response.as_dict())
            return

        if http_response is None or http_response.body is None or not isinstance(http_response.body, (str, unicode)):
            _logger.error("Unable to download web page of project: Invalid or empty HTML-content!")
            self.write(ProjectDataResponse().as_dict())
            return

        #body = re.sub("(.*" + re.escape("<li>") + r'\s*' + re.escape("<div class=\"project thumb\">") + r'.*' + re.escape("<span class=\"owner\">") + r'.*' + re.escape("</span>") + r'\s*' + ")" + "(" + re.escape("</li>.*") + ")", r'\1</div>\2', http_response.body)
        document = _ResponseBeautifulSoupDocumentWrapper(BeautifulSoup(http_response.body, b'html5lib'))
        visibility_state = scratchwebapi.extract_project_visibilty_state_from_document(document)
        response = ProjectDataResponse()
        response.accessible = True
        response.visibility_state = visibility_state
        response.valid_until = dt.now() + timedelta(seconds=cls.CACHE_ENTRY_VALID_FOR)

        if visibility_state != ScratchProjectVisibiltyState.PUBLIC:
            _logger.warn("Not allowed to access non-public scratch-project!")
            cls.response_cache[project_id] = response
            self.write(response.as_dict())
            return

        project_info = scratchwebapi.extract_project_details_from_document(document)
        if project_info is None:
            _logger.error("Unable to parse project-info from web page: Invalid or empty HTML-content!")
            self.write(response.as_dict())
            return

        response.project_data = project_info.as_dict()
        cls.response_cache[project_id] = response
        self.write(response.as_dict())
        return


class ConverterWebApp(tornado.web.Application):
    def __init__(self, **settings):
        self.settings = settings
        handlers = [
            (r"/", _MainHandler),
            (r"/download", _DownloadHandler),
            (r"/convertersocket", ConverterWebSocketHandler),
            (r"/api/v1/projects/?", _ProjectHandler),
            (r"/api/v1/projects/(\d+)/?", _ProjectHandler),
        ]
        httpclient.AsyncHTTPClient.configure(None, defaults=dict(user_agent=HTTP_USER_AGENT))
        self.async_http_client = httpclient.AsyncHTTPClient()
        tornado.web.Application.__init__(self, handlers, **settings)

#!/bin/env python2
from __future__ import print_function
from pprint import pprint
import sys
import urllib
import json
import websocket

DEFAULT_HOST = 'localhost'
DEFAULT_JOB_ID = 10205819
DEFAULT_FORCE = 0
DEFAULT_OUTPUT_DIRECTORY = "."

argc = len(sys.argv)

host = sys.argv[1] if argc > 1 else DEFAULT_HOST
job_id = int(sys.argv[2]) if argc > 2 else DEFAULT_JOB_ID
force = int(bool(sys.argv[3])) if argc > 3 else DEFAULT_FORCE
output_directory = sys.argv[4] if argc > 4 else DEFAULT_OUTPUT_DIRECTORY

ws_url = "ws://{}/convertersocket".format(host)
ws = websocket.create_connection(ws_url)

#handshake for client_id
ws_auth_data = { "cmd": 0, "args": { "clientID": float("NaN") } }
ws.send(json.dumps(ws_auth_data))
handshake_recv_data = json.loads(ws.recv())
client_id = handshake_recv_data["data"]["clientID"]
print("Client ID: {}".format(client_id))

#schedule job
ws_schedule_data = {
    "cmd": 2,
    "args": {
      "jobID": job_id,
      "force": force,
      "verbose": False
    }
}
ws.send(json.dumps(ws_schedule_data))

#wait for finished or error response
while True:
    job_info = json.loads(ws.recv())
    pprint(job_info)
    if job_info["category"] == 1 and job_info["data"]["jobID"] == job_id:
        if job_info["type"] == 0: #Error
            print("ERROR")
            sys.exit(1)
        if job_info["type"] == 6: #Finished
            url = "http://{}{}".format(host, job_info["data"]["url"])
            break

#download resulting object
print("url: {}".format(url))
result = urllib.urlopen(url)
filename = "{}/{}_{}.catrobat".format(output_directory, job_id, client_id)
print("Writing file to {}".format(filename))
with open(filename, 'w') as f:
    f.write(result.read())

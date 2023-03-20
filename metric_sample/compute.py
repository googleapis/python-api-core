from google.cloud import compute_v1
import os

import logging
from http.client import HTTPConnection

def debug_requests_on():
    '''Switches on logging of the requests module.'''
    HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

debug_requests_on()

os.environ["my_client"] = "http"
instance_client = compute_v1.InstancesClient()
instance_list = instance_client.list(project="sijunliu-nondca-test", zone="us-west3-b")
print(instance_list)
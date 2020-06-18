# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Client options class.

Client options provide a consistent interface for user options to be defined
across clients.

You can pass a client options object to a client.

.. code-block:: python

    from google.api_core.client_options import ClientOptions
    from google.cloud.vision_v1 import ImageAnnotatorClient

    options = ClientOptions(api_endpoint="foo.googleapis.com")

    client = ImageAnnotatorClient(client_options=options)

You can also pass a mapping object.

.. code-block:: python

    from google.cloud.vision_v1 import ImageAnnotatorClient

    client = ImageAnnotatorClient(client_options={"api_endpoint": "foo.googleapis.com"})


"""


class ClientOptions(object):
    """Client Options used to set options on clients.

    Args:
        api_endpoint (str): The desired API endpoint, e.g., compute.googleapis.com
    """

    def __init__(self, api_endpoint=None):
        self.api_endpoint = api_endpoint

    def __repr__(self):
        return "ClientOptions: " + repr(self.__dict__)


def from_dict(options):
    """Construct a client options object from a mapping object.

    Args:
        options (six.moves.collections_abc.Mapping): A mapping object with client options.
    """

    client_options = ClientOptions()

    for key, value in options.items():
        if hasattr(client_options, key):
            setattr(client_options, key, value)
        else:
            raise ValueError("ClientOptions does not accept an option '" + key + "'")

    return client_options

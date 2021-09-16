# Copyright 2017 Google LLC
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

"""Helpers for rest transports."""

import itertools


def flatten_query_params(obj, key_path=[]):
    """Flatten a nested dict into a list of (name,value) tuples.

    The result is suitable for setting query params on an http request.

    .. code-block:: python

        >>> obj = {'a':
        ...         {'b':
        ...           {'c': ['x', 'y', 'z']} },
        ...      'd': 'uvw', }
        >>> flatten_query_params(obj)
        [('a.b.c', 'x'), ('a.b.c', 'y'), ('a.b.c', 'z'), ('d', 'uvw')]

    Args:
      obj: a nested dictionary (from json)
      key_path: a list of name segments, representing levels above this obj.

    Returns: a list of tuples, with each tuple having a (possibly) multi-part name
      and a scalar value.
    """

    if obj is None:
        return []
    if isinstance(obj, dict):
        return _flatten_dict(obj, key_path=key_path)
    if isinstance(obj, list):
        return _flatten_list(obj, key_path=key_path)
    return _flatten_value(obj, key_path=key_path)


def _is_value(obj):
    if obj is None:
        return False
    return not (isinstance(obj, list) or isinstance(obj, dict))


def _flatten_value(obj, key_path=[]):
    if not key_path:
        # There must be a key.
        return []
    return [('.'.join(key_path), obj)]


def _flatten_dict(obj, key_path=[]):
    return list(
        itertools.chain(*(flatten_query_params(v, key_path=key_path + [k])
                        for k, v in obj.items())))


def _flatten_list(l, key_path=[]):
    # Only lists of scalar values are supported.
    # The name (key_path) is repeated for each value.
    return list(
        itertools.chain(*(_flatten_value(elem, key_path=key_path)
                          for elem in l
                          if _is_value(elem))))

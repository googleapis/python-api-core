# Copyright 2021 Google LLC
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

from google.api_core import rest_helpers


def test_flatten_none():
    assert rest_helpers.flatten_query_params(None) == []


def test_flatten_empty_dict():
    assert rest_helpers.flatten_query_params({}) == []


def test_flatten_simple_dict():
    assert rest_helpers.flatten_query_params({'a': 'abc', 'b': 'def'}) == [
        ('a', 'abc'), ('b', 'def')]


def test_flatten_repeated_field():
    assert rest_helpers.flatten_query_params({'a': ['x', 'y', 'z']}) == [
        ('a', 'x'), ('a', 'y'), ('a', 'z')]


def test_flatten_nested_dict():
    obj = {'a':
           {'b':
            {'c': ['x', 'y', 'z']}},
           'd':
           {'e': 'uvw'}}
    expected_result = [('a.b.c', 'x'),
                       ('a.b.c', 'y'),
                       ('a.b.c', 'z'),
                       ('d.e', 'uvw')]

    assert rest_helpers.flatten_query_params(obj) == expected_result


def test_flatten_ignore_repeated_dict():
    obj = {'a':
           {'b':
            {'c':
             [{'v': 1}, {'v': 2}]
             }
            },
           'd': 'uvw', }
    # a.b.c is a repeated dict - ignored
    expected_result = [('d', 'uvw')]

    assert rest_helpers.flatten_query_params(obj) == expected_result

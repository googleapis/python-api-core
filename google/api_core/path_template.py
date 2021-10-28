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

"""Expand and validate URL path templates. Transform path template into RegEx.

This module provides the :func:`expand` and :func:`validate` functions for
interacting with Google-style URL `path templates`_ which are commonly used
in Google APIs for `resource names`_. It also provides the :func:`to_regex`
function for converting `path template` into a corresponding RegEx that
matches resource names conforming to the pattern in `path template`.

.. _path templates: https://github.com/googleapis/googleapis/blob
    /57e2d376ac7ef48681554204a3ba78a414f2c533/google/api/http.proto#L212
.. _resource names: https://cloud.google.com/apis/design/resource_names
"""

from __future__ import unicode_literals

from collections import deque
import copy
import functools
import re
from typing import Pattern

# Regular expression for extracting variable parts from a path template.
# The variables can be expressed as:
#
# - "*": a single-segment positional variable, for example: "books/*"
# - "**": a multi-segment positional variable, for example: "shelf/**/book/*"
# - "{name}": a single-segment wildcard named variable, for example
#   "books/{name}"
# - "{name=*}: same as above.
# - "{name=**}": a multi-segment wildcard named variable, for example
#   "shelf/{name=**}"
# - "{name=/path/*/**}": a multi-segment named variable with a sub-template.
_VARIABLE_RE = re.compile(
    r"""
    (  # Capture the entire variable expression
        (?P<positional>\*\*?)  # Match & capture * and ** positional variables.
        |
        # Match & capture named variables {name}
        {
            (?P<name>[^/]+?)
            # Optionally match and capture the named variable's template.
            (?:=(?P<template>.+?))?
        }
    )
    """,
    re.VERBOSE,
)

# Segment expressions used for validating paths against a template.
_SINGLE_SEGMENT_PATTERN = r"([^/]+)"
_MULTI_SEGMENT_PATTERN = r"(.+)"


def _expand_variable_match(positional_vars, named_vars, match):
    """Expand a matched variable with its value.

    Args:
        positional_vars (list): A list of positional variables. This list will
            be modified.
        named_vars (dict): A dictionary of named variables.
        match (re.Match): A regular expression match.

    Returns:
        str: The expanded variable to replace the match.

    Raises:
        ValueError: If a positional or named variable is required by the
            template but not specified or if an unexpected template expression
            is encountered.
    """
    positional = match.group("positional")
    name = match.group("name")
    if name is not None:
        try:
            return str(named_vars[name])
        except KeyError:
            raise ValueError(
                "Named variable '{}' not specified and needed by template "
                "`{}` at position {}".format(name, match.string, match.start())
            )
    elif positional is not None:
        try:
            return str(positional_vars.pop(0))
        except IndexError:
            raise ValueError(
                "Positional variable not specified and needed by template "
                "`{}` at position {}".format(match.string, match.start())
            )
    else:
        raise ValueError("Unknown template expression {}".format(match.group(0)))


def expand(tmpl, *args, **kwargs):
    """Expand a path template with the given variables.

    .. code-block:: python

        >>> expand('users/*/messages/*', 'me', '123')
        users/me/messages/123
        >>> expand('/v1/{name=shelves/*/books/*}', name='shelves/1/books/3')
        /v1/shelves/1/books/3

    Args:
        tmpl (str): The path template.
        args: The positional variables for the path.
        kwargs: The named variables for the path.

    Returns:
        str: The expanded path

    Raises:
        ValueError: If a positional or named variable is required by the
            template but not specified or if an unexpected template expression
            is encountered.
    """
    replacer = functools.partial(_expand_variable_match, list(args), kwargs)
    return _VARIABLE_RE.sub(replacer, tmpl)


def _replace_variable_with_pattern(match):
    """Replace a variable match with a pattern that can be used to validate it.

    Args:
        match (re.Match): A regular expression match

    Returns:
        str: A regular expression pattern that can be used to validate the
            variable in an expanded path.

    Raises:
        ValueError: If an unexpected template expression is encountered.
    """
    positional = match.group("positional")
    name = match.group("name")
    template = match.group("template")
    if name is not None:
        if not template:
            return _SINGLE_SEGMENT_PATTERN.format(name)
        elif template == "**":
            return _MULTI_SEGMENT_PATTERN.format(name)
        else:
            return _generate_pattern_for_template(template)
    elif positional == "*":
        return _SINGLE_SEGMENT_PATTERN
    elif positional == "**":
        return _MULTI_SEGMENT_PATTERN
    else:
        raise ValueError("Unknown template expression {}".format(match.group(0)))


def _generate_pattern_for_template(tmpl):
    """Generate a pattern that can validate a path template.

    Args:
        tmpl (str): The path template

    Returns:
        str: A regular expression pattern that can be used to validate an
            expanded path template.
    """
    return _VARIABLE_RE.sub(_replace_variable_with_pattern, tmpl)


def get_field(request, field):
    """Get the value of a field from a given dictionary.

    Args:
        request (dict): A dictionary object.
        field (str): The key to the request in dot notation.

    Returns:
        The value of the field.
    """
    parts = field.split(".")
    value = request
    for part in parts:
        if not isinstance(value, dict):
            return
        value = value.get(part)
    if isinstance(value, dict):
        return
    return value


def delete_field(request, field):
    """Delete the value of a field from a given dictionary.

    Args:
        request (dict): A dictionary object.
        field (str): The key to the request in dot notation.
    """
    parts = deque(field.split("."))
    while len(parts) > 1:
        if not isinstance(request, dict):
            return
        part = parts.popleft()
        request = request.get(part)
    part = parts.popleft()
    if not isinstance(request, dict):
        return
    request.pop(part, None)


def validate(tmpl, path):
    """Validate a path against the path template.

    .. code-block:: python

        >>> validate('users/*/messages/*', 'users/me/messages/123')
        True
        >>> validate('users/*/messages/*', 'users/me/drafts/123')
        False
        >>> validate('/v1/{name=shelves/*/books/*}', /v1/shelves/1/books/3)
        True
        >>> validate('/v1/{name=shelves/*/books/*}', /v1/shelves/1/tapes/3)
        False

    Args:
        tmpl (str): The path template.
        path (str): The expanded path.

    Returns:
        bool: True if the path matches.
    """
    pattern = _generate_pattern_for_template(tmpl) + "$"
    return True if re.match(pattern, path) is not None else False


def transcode(http_options, **request_kwargs):
    """Transcodes a grpc request pattern into a proper HTTP request following the rules outlined here,
       https://github.com/googleapis/googleapis/blob/master/google/api/http.proto#L44-L312

        Args:
            http_options (list(dict)): A list of dicts which consist of these keys,
                'method'    (str): The http method
                'uri'       (str): The path template
                'body'      (str): The body field name (optional)
                (This is a simplified representation of the proto option `google.api.http`)

            request_kwargs (dict) : A dict representing the request object

        Returns:
            dict: The transcoded request with these keys,
                'method'        (str)   : The http method
                'uri'           (str)   : The expanded uri
                'body'          (dict)  : A dict representing the body (optional)
                'query_params'  (dict)  : A dict mapping query parameter variables and values

        Raises:
            ValueError: If the request does not match the given template.
    """
    for http_option in http_options:
        request = {}

        # Assign path
        uri_template = http_option["uri"]
        path_fields = [
            match.group("name") for match in _VARIABLE_RE.finditer(uri_template)
        ]
        path_args = {field: get_field(request_kwargs, field) for field in path_fields}
        request["uri"] = expand(uri_template, **path_args)

        # Remove fields used in uri path from request
        leftovers = copy.deepcopy(request_kwargs)
        for path_field in path_fields:
            delete_field(leftovers, path_field)

        if not validate(uri_template, request["uri"]) or not all(path_args.values()):
            continue

        # Assign body and query params
        body = http_option.get("body")

        if body:
            if body == "*":
                request["body"] = leftovers
                request["query_params"] = {}
            else:
                try:
                    request["body"] = leftovers.pop(body)
                except KeyError:
                    continue
                request["query_params"] = leftovers
        else:
            request["query_params"] = leftovers
        request["method"] = http_option["method"]
        return request

    raise ValueError("Request obj does not match any template")


def _split_into_segments(path_template):
    segments = path_template.split("/")
    named_segment_ids = [i for i, x in enumerate(segments) if "{" in x or "}" in x]
    # bar/{foo}/baz, bar/{foo=one/two/three}/baz.
    assert len(named_segment_ids) <= 2
    if len(named_segment_ids) == 2:
        # Need to merge a named segment.
        i, j = named_segment_ids
        segments = (
            segments[:i] + [_merge_segments(segments[i : j + 1])] + segments[j + 1 :]
        )
    return segments


def _convert_segment_to_regex(segment):
    # Named segment
    if "{" in segment:
        assert "}" in segment
        # Strip "{" and "}"
        segment = segment[1:-1]
        if "=" not in segment:
            # e.g. {foo} should be {foo=*}
            return _convert_segment_to_regex("{" + f"{segment}=*" + "}")
        key, sub_path_template = segment.split("=")
        group_name = f"?P<{key}>"
        sub_regex = _convert_to_regex(sub_path_template)
        return f"({group_name}{sub_regex})"
    # Wildcards
    if "**" in segment:
        # ?: nameless capture
        return ".*"
    if "*" in segment:
        return "[^/]+"
    # Otherwise it's collection ID segment: transformed identically.
    return segment


def _merge_segments(segments):
    acc = segments[0]
    for x in segments[1:]:
        # Don't add "/" if it's followed by a "**"
        # because "**" will eat it.
        if x == ".*":
            acc += "(?:/.*)?"
        else:
            acc += "/"
            acc += x
    return acc


def _how_many_named_segments(path_template: str) -> int:
    return path_template.count("{")


def _convert_to_regex(path_template) -> str:
    if _how_many_named_segments(path_template) > 1:
        # This also takes care of complex patterns (i.e. {foo}~{bar})
        raise ValueError("There should be exactly one named segment.")
    segments = _split_into_segments(path_template)
    segment_regexes = [_convert_segment_to_regex(x) for x in segments]
    final_regex = _merge_segments(segment_regexes)
    return final_regex


def to_regex(path_template: str) -> Pattern:
    """Converts path_template into a Python regular expression string.

    For the different types of the segments in the pattern, the conversion is as follows:
    - Collection id segments
        The literals, e.g. projects or databases. They are transformed to the regex literally.
    - The wildcard patterns: * and **.
        The * pattern corresponds to 1 or more non-/ symbols. The regex describing it is [^/]+
        The ** pattern corresponds to 0 or more segments (so it can be empty).
        The regex is technically .*, but since it should only match a leading / if it has
        any other content (e.g. documents/**/index should match documents/index, and not documents//index),
        it is slightly more complicated, roughly at (/.*)?.
    - The named segments: {foo} and {foo=pattern}
        {foo} is equivalent to {foo=*}.
        {foo=pattern}. The pattern cannot contain another named segment,
        and the regex generation for it is recursive. The sub-pattern regex is enclosed
        in a capture group because then the combined regex can be used for both matching and extraction.

    .. code-block:: python

        >>> to_regex('{database=projects/*/databases/*}/documents/*/**')
        ^(?P<database>projects/[^/]+/databases/[^/]+)/documents/[^/]+(?:/.*)?$
        >>> to_regex('{foo=**}')
        ^(?P<foo>.*)$
        >>> to_regex('hello/*/**')
        ^hello/[^/]+(?:/.*)?$
        >>> to_regex('{song=artists/*/{albums}/*/**}')
        ValueError('There should be exactly one named segment.')
        >>> to_regex('{database=projects/*/databases/*/**}/documents/{document=databases/*/documents/*/**}/*/**')
        ValueError('There should be exactly one named segment.')

    Args:
        path_template (str): A path template corresponding to a resource name. It can only
        have 0 or 1 named segments. It can not contain complex resource ID path segments.
        See https://google.aip.dev/122 and https://google.aip.dev/client-libraries/4231 for more details.
    Returns:
        Pattern: A Pattern object that matches strings conforming to the path_template.
    """
    return re.compile(f"^{_convert_to_regex(path_template)}$")

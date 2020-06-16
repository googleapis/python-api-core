# (generated with --quick)

import __future__
from typing import Pattern

_MULTI_SEGMENT_PATTERN: str
_SINGLE_SEGMENT_PATTERN: str
_VARIABLE_RE: Pattern[str]
functools: module
re: module
six: module
unicode_literals: __future__._Feature

def _expand_variable_match(positional_vars, named_vars, match) -> str: ...
def _generate_pattern_for_template(tmpl) -> str: ...
def _replace_variable_with_pattern(match) -> str: ...
def expand(tmpl, *args, **kwargs) -> str: ...
def validate(tmpl, path) -> bool: ...

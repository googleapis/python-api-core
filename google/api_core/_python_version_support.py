# Copyright 2025 Google LLC
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

"""Code to check Python versions supported by Google Cloud Client Libraries."""

import datetime
import enum
import logging
import sys
import textwrap
from typing import NamedTuple, Optional, Dict, Tuple


class PythonVersionStatus(enum.Enum):
    """Represent the support status of a Python version."""

    PYTHON_VERSION_UNSUPPORTED = "PYTHON_VERSION_UNSUPPORTED"
    PYTHON_VERSION_EOL = "PYTHON_VERSION_EOL"
    PYTHON_VERSION_DEPRECATED = "PYTHON_VERSION_DEPRECATED"
    PYTHON_VERSION_SUPPORTED = "PYTHON_VERSION_SUPPORTED"


class VersionInfo(NamedTuple):
    """Hold release and support date information for a Python version."""

    python_beta: Optional[datetime.date]
    python_start: datetime.date
    python_eol: datetime.date
    gapic_start: Optional[datetime.date] = None  # unused
    gapic_deprecation: Optional[datetime.date] = None
    gapic_end: Optional[datetime.date] = None
    dep_unpatchable_cve: Optional[datetime.date] = None  # unused


PYTHON_VERSION_INFO: Dict[Tuple[int, int], VersionInfo] = {
    # Refer to https://devguide.python.org/versions/ and the PEPs linked therefrom.
    (3, 7): VersionInfo(
        python_beta=None,
        python_start=datetime.date(2018, 6, 27),
        python_eol=datetime.date(2023, 6, 27),
    ),
    (3, 8): VersionInfo(
        python_beta=None,
        python_start=datetime.date(2019, 10, 14),
        python_eol=datetime.date(2024, 10, 7),
    ),
    (3, 9): VersionInfo(
        python_beta=datetime.date(2020, 5, 18),
        python_start=datetime.date(2020, 10, 5),
        python_eol=datetime.date(2025, 10, 5),  # TODO: specify day when announced
    ),
    (3, 10): VersionInfo(
        python_beta=datetime.date(2021, 5, 3),
        python_start=datetime.date(2021, 10, 4),
        python_eol=datetime.date(2026, 10, 4),  # TODO: specify day when announced
    ),
    (3, 11): VersionInfo(
        python_beta=datetime.date(2022, 5, 8),
        python_start=datetime.date(2022, 10, 24),
        python_eol=datetime.date(2027, 10, 24),  # TODO: specify day when announced
    ),
    (3, 12): VersionInfo(
        python_beta=datetime.date(2023, 5, 22),
        python_start=datetime.date(2023, 10, 2),
        python_eol=datetime.date(2028, 10, 2),  # TODO: specify day when announced
    ),
    (3, 13): VersionInfo(
        python_beta=datetime.date(2024, 5, 8),
        python_start=datetime.date(2024, 10, 7),
        python_eol=datetime.date(2029, 10, 7),  # TODO: specify day when announced
    ),
    (3, 14): VersionInfo(
        python_beta=datetime.date(2025, 5, 7),
        python_start=datetime.date(2025, 10, 7),
        python_eol=datetime.date(2030, 10, 7),  # TODO: specify day when announced
    ),
}

LOWEST_TRACKED_VERSION = min(PYTHON_VERSION_INFO.keys())
FAKE_PAST_DATE = datetime.date(1970, 1, 1)
FAKE_FUTURE_DATE = datetime.date(9000, 1, 1)


def _flatten_message(text: str) -> str:
    """Dedent a multi-line string and flattens it into a single line."""
    return textwrap.dedent(text).strip().replace("\n", " ")


def check_python_version(
    package: Optional[str] = "this package", today: Optional[datetime.date] = None
) -> PythonVersionStatus:
    """Check the running Python version and issue a support warning if needed.

    Args:
        today: The date to check against. Defaults to the current date.

    Returns:
        The support status of the current Python version.
    """
    today = today or datetime.date.today()

    python_version = sys.version_info
    version_tuple = (python_version.major, python_version.minor)
    py_version_str = f"{python_version.major}.{python_version.minor}"

    version_info = PYTHON_VERSION_INFO.get(version_tuple)

    if not version_info:
        if version_tuple < LOWEST_TRACKED_VERSION:
            version_info = VersionInfo(
                python_beta=FAKE_PAST_DATE,
                python_start=FAKE_PAST_DATE,
                python_eol=FAKE_PAST_DATE,
            )
        else:
            version_info = VersionInfo(
                python_beta=FAKE_FUTURE_DATE,
                python_start=FAKE_FUTURE_DATE,
                python_eol=FAKE_FUTURE_DATE,
            )

    gapic_deprecation = version_info.gapic_deprecation or (
        version_info.python_eol - datetime.timedelta(days=365)
    )
    gapic_end = version_info.gapic_end or (
        version_info.python_eol + datetime.timedelta(weeks=1)
    )

    def min_python(date: datetime.date) -> str:
        """Find the minimum supported Python version for a given date."""
        for version, info in sorted(PYTHON_VERSION_INFO.items()):
            if info.python_start <= date < info.python_eol:
                return f"{version[0]}.{version[1]}"
        return "at a supported version"

    if gapic_end < today:
        message = _flatten_message(
            f"""
            You are using a non-supported Python version ({py_version_str}).
            Google will not post any further updates to {package}. We suggest
            you upgrade to the latest Python version, or at least Python
            {min_python(today)}, and then update {package}.
            """
        )
        logging.warning(message)
        return PythonVersionStatus.PYTHON_VERSION_UNSUPPORTED

    eol_date = version_info.python_eol + datetime.timedelta(weeks=1)
    if eol_date <= today <= gapic_end:
        message = _flatten_message(
            f"""
            You are using a Python version ({py_version_str}) past its end
            of life. Google will update {package} with critical
            bug fixes on a best-effort basis, but not with any other fixes or
            features. We suggest you upgrade to the latest Python version,
            or at least Python {min_python(today)}, and then update {package}.
            """
        )
        logging.warning(message)
        return PythonVersionStatus.PYTHON_VERSION_EOL

    if gapic_deprecation <= today <= gapic_end:
        message = _flatten_message(
            f"""
            You are using a Python version ({py_version_str}),
            which Google will stop supporting in {package} when it
            reaches its end of life ({version_info.python_eol}). We
            suggest you upgrade to the latest Python version, or at
            least Python {min_python(version_info.python_eol)}, and
            then update {package}.
            """
        )
        logging.warning(message)
        return PythonVersionStatus.PYTHON_VERSION_DEPRECATED

    return PythonVersionStatus.PYTHON_VERSION_SUPPORTED

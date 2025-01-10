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

import pytest
pytest.importorskip("opentelemetry")
from google.api_core.metrics_tracer import MetricsTracer, MetricOpTracer
import mock
from opentelemetry.metrics import Counter, Histogram
from datetime import datetime

@pytest.fixture
def metrics_tracer():
    mock_attempt_counter = mock.create_autospec(Counter, instance=True)
    mock_attempt_latency = mock.create_autospec(Histogram, instance=True)
    mock_operation_counter = mock.create_autospec(Counter, instance=True)
    mock_operation_latency = mock.create_autospec(Histogram, instance=True)
    return MetricsTracer(
        method="test_method",
        enabled=True,
        is_direct_path_enabled=False,
        instrument_attempt_latency=mock_attempt_latency,
        instrument_attempt_counter=mock_attempt_counter,
        instrument_operation_latency=mock_operation_latency,
        instrument_operation_counter=mock_operation_counter,
        client_attributes={"project_id": "test_project"},
    )


def test_initialization(metrics_tracer):
    assert metrics_tracer.method == "test_method"
    assert metrics_tracer.enabled is True


def test_record_attempt_start(metrics_tracer):
    metrics_tracer.record_attempt_start()
    assert metrics_tracer.current_op.current_attempt is not None
    assert metrics_tracer.current_op.current_attempt.start_time is not None
    assert metrics_tracer.current_op.attempt_count == 1


def test_record_operation_start(metrics_tracer):
    metrics_tracer.record_operation_start()
    assert metrics_tracer.current_op.start_time is not None


def test_record_attempt_completion(metrics_tracer):
    metrics_tracer.record_attempt_start()
    metrics_tracer.record_attempt_completion()
    assert metrics_tracer.current_op.current_attempt.status == "OK"


def test_record_operation_completion(metrics_tracer):
    metrics_tracer.record_operation_start()
    metrics_tracer.record_attempt_start()
    metrics_tracer.record_attempt_completion()
    metrics_tracer.record_operation_completion()
    assert metrics_tracer.instrument_attempt_counter.add.call_count == 1
    assert metrics_tracer.instrument_attempt_latency.record.call_count == 1
    assert metrics_tracer.instrument_operation_latency.record.call_count == 1
    assert metrics_tracer.instrument_operation_counter.add.call_count == 1


def test_atempt_otel_attributes(metrics_tracer):
    from google.api_core.metrics_tracer import (
        METRIC_LABEL_KEY_DIRECT_PATH_USED,
        METRIC_LABEL_KEY_STATUS,
    )

    metrics_tracer.current_op._current_attempt = None
    attributes = metrics_tracer._create_attempt_otel_attributes()
    assert METRIC_LABEL_KEY_DIRECT_PATH_USED not in attributes


def test_disabled(metrics_tracer):
    mock_operation = mock.create_autospec(MetricOpTracer, instance=True)
    metrics_tracer.enabled = False
    metrics_tracer._current_op = mock_operation

    # Attempt start should be skipped
    metrics_tracer.record_attempt_start()
    assert mock_operation.new_attempt.call_count == 0

    # Attempt completion should also be skipped
    metrics_tracer.record_attempt_completion()
    assert metrics_tracer.instrument_attempt_latency.record.call_count == 0

    # Operation start should be skipped
    metrics_tracer.record_operation_start()
    assert mock_operation.start.call_count == 0

    # Operation completion should also skip all metric logic
    metrics_tracer.record_operation_completion()
    assert metrics_tracer.instrument_attempt_counter.add.call_count == 0
    assert metrics_tracer.instrument_operation_latency.record.call_count == 0
    assert metrics_tracer.instrument_operation_counter.add.call_count == 0

    assert metrics_tracer._create_otel_attributes() is None
    assert metrics_tracer._create_operation_otel_attributes() is None
    assert metrics_tracer._create_attempt_otel_attributes() is None


def test_get_ms_time_diff():
    # Create two datetime objects
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = datetime(2025, 1, 1, 12, 0, 1)  # 1 second later

    # Calculate expected milliseconds difference
    expected_diff = 1000.0  # 1 second in milliseconds

    # Call the static method
    actual_diff = MetricsTracer._get_ms_time_diff(start_time, end_time)

    # Assert the expected and actual values are equal
    assert actual_diff == expected_diff


def test_get_ms_time_diff_negative():
    # Create two datetime objects where end is before start
    start_time = datetime(2025, 1, 1, 12, 0, 1)
    end_time = datetime(2025, 1, 1, 12, 0, 0)  # 1 second earlier

    # Calculate expected milliseconds difference
    expected_diff = -1000.0  # -1 second in milliseconds

    # Call the static method
    actual_diff = MetricsTracer._get_ms_time_diff(start_time, end_time)

    # Assert the expected and actual values are equal
    assert actual_diff == expected_diff

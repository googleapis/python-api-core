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

"""This module contains the MetricTracer class and its related helper classes. 
The MetricTracer class is responsible for collecting and tracing metrics, 
while the helper classes provide additional functionality and context for the metrics being traced."""

from datetime import datetime
from typing import Dict

try:
    from opentelemetry.metrics import Counter, Histogram

    HAS_OPENTELEMETRY_INSTALLED = True
except ImportError:  # pragma: NO COVER
    HAS_OPENTELEMETRY_INSTALLED = False

import http.client

# Monitored Resource Labels
MONITORED_RES_LABEL_KEY_PROJECT = "project_id"
MONITORED_RES_LABEL_KEY_INSTANCE = "instance_id"
MONITORED_RES_LABEL_KEY_INSTANCE_CONFIG = "instance_config"
MONITORED_RES_LABEL_KEY_LOCATION = "location"
MONITORED_RES_LABEL_KEY_CLIENT_HASH = "client_hash"
# Metric Labels
METRIC_LABEL_KEY_CLIENT_UID = "client_uid"
METRIC_LABEL_KEY_CLIENT_NAME = "client_name"
METRIC_LABEL_KEY_DATABASE = "database"
METRIC_LABEL_KEY_METHOD = "method"
METRIC_LABEL_KEY_STATUS = "status"
METRIC_LABEL_KEY_DIRECT_PATH_ENABLED = "directpath_enabled"
METRIC_LABEL_KEY_DIRECT_PATH_USED = "directpath_used"


class MetricAttemptTracer:
    """This class is designed to hold information related to a metric attempt.
    It captures the start time of the attempt, whether the direct path was used, and the status of the attempt."""

    _start_time: datetime
    direct_path_used: bool
    status: str

    def __init__(self):
        """
        Initializes a MetricAttemptTracer instance with default values.

        This constructor sets the start time of the metric attempt to the current datetime, initializes the status as an empty string, and sets direct path used flag to False by default.
        """
        self._start_time = datetime.now()
        self.status = ""
        self.direct_path_used = False

    @property
    def start_time(self):
        """Getter method for the start_time property.

        This method returns the start time of the metric attempt.

        Returns:
            datetime: The start time of the metric attempt.
        """
        return self._start_time


class MetricOpTracer:
    """
    This class is designed to store and manage information related to metric operations.
    It captures the method name, start time, attempt count, current attempt, status, and direct path enabled status of a metric operation.
    """

    _attempt_count: int
    _start_time: datetime
    _current_attempt: MetricAttemptTracer
    status: str
    direct_path_enabled: bool

    def __init__(self, is_direct_path_enabled: bool = False):
        """
        Initializes a MetricOpTracer instance with the given parameters.

        This constructor sets up a MetricOpTracer instance with the provided metric name, instrumentations for attempt latency,
        attempt counter, operation latency, and operation counter, and a flag indicating whether the direct path is enabled.
        It initializes the method name, start time, attempt count, current attempt, direct path enabled status, and status of the metric operation.

        Args:
            metric_name (str): The name of the metric operation.
            instrument_attempt_latency (Histogram): The instrumentation for measuring attempt latency.
            instrument_attempt_counter (Counter): The instrumentation for counting attempts.
            instrument_operation_latency (Histogram): The instrumentation for measuring operation latency.
            instrument_operation_counter (Counter): The instrumentation for counting operations.
            is_direct_path_enabled (bool, optional): A flag indicating whether the direct path is enabled. Defaults to False.
        """
        self._attempt_count = 0
        self._start_time = datetime.now()
        self._current_attempt = None
        self.direct_path_enabled = is_direct_path_enabled
        self.status = ""

    @property
    def attempt_count(self):
        return self._attempt_count

    @property
    def current_attempt(self):
        return self._current_attempt

    @property
    def start_time(self):
        return self._start_time

    def increment_attempt_count(self):
        self._attempt_count += 1

    def start(self):
        self._start_time = datetime.now()

    def new_attempt(self):
        self._current_attempt = MetricAttemptTracer()


class MetricsTracer:
    """
    This class computes generic metrics that can be observed in the lifecycle of an RPC operation.

    The responsibility of recording metrics should delegate to MetricsRecorder, hence this
    class should not have any knowledge about the observability framework used for metrics recording.
    """

    _client_attributes: Dict[str, str]
    _instrument_attempt_counter: Counter
    _instrument_attempt_latency: Histogram
    _instrument_operation_counter: Counter
    _instrument_operation_latency: Histogram
    current_op: MetricOpTracer
    enabled: bool
    method: str

    def __init__(
        self,
        method: str,
        enabled: bool,
        is_direct_path_enabled: bool,
        instrument_attempt_latency: Histogram,
        instrument_attempt_counter: Counter,
        instrument_operation_latency: Histogram,
        instrument_operation_counter: Counter,
        client_attributes: Dict[str, str],
    ):
        """
        Initializes a MetricsTracer instance with the given parameters.

        This constructor initializes a MetricsTracer instance with the provided method name, enabled status, direct path enabled status,
        instrumented metrics for attempt latency, attempt counter, operation latency, operation counter, and client attributes.
        It sets up the necessary metrics tracing infrastructure for recording metrics related to RPC operations.

        Args:
            method (str): The name of the method for which metrics are being traced.
            enabled (bool): A flag indicating if metrics tracing is enabled.
            is_direct_path_enabled (bool): A flag indicating if the direct path is enabled for metrics tracing.
            instrument_attempt_latency (Histogram): The instrument for measuring attempt latency.
            instrument_attempt_counter (Counter): The instrument for counting attempts.
            instrument_operation_latency (Histogram): The instrument for measuring operation latency.
            instrument_operation_counter (Counter): The instrument for counting operations.
            client_attributes (dict[str, str]): A dictionary of client attributes used for metrics tracing.
        """
        self.method = method
        self.current_op = MetricOpTracer(is_direct_path_enabled=is_direct_path_enabled)
        self._client_attributes = client_attributes
        self._instrument_attempt_latency = instrument_attempt_latency
        self._instrument_attempt_counter = instrument_attempt_counter
        self._instrument_operation_latency = instrument_operation_latency
        self._instrument_operation_counter = instrument_operation_counter
        self.enabled = enabled

    @property
    def client_attributes(self) -> Dict[str, str]:
        """
        Returns a dictionary of client attributes used for metrics tracing.

        This property returns a dictionary containing client attributes such as project, instance,
        instance configuration, location, client hash, client UID, client name, and database.
        These attributes are used to provide context to the metrics being traced.

        Returns:
            dict[str, str]: A dictionary of client attributes.
        """
        return self._client_attributes

    @property
    def instrument_attempt_counter(self) -> Counter:
        """
        Returns the instrument for counting attempts.

        This property returns the Counter instrument used to count the number of attempts made during RPC operations.
        This metric is useful for tracking the frequency of attempts and can help identify patterns or issues in the operation flow.

        Returns:
            Counter: The instrument for counting attempts.
        """
        return self._instrument_attempt_counter

    @property
    def instrument_attempt_latency(self) -> Histogram:
        """
        Returns the instrument for measuring attempt latency.

        This property returns the Histogram instrument used to measure the latency of individual attempts.
        This metric is useful for tracking the performance of attempts and can help identify bottlenecks or issues in the operation flow.

        Returns:
            Histogram: The instrument for measuring attempt latency.
        """
        return self._instrument_attempt_latency

    @property
    def instrument_operation_counter(self) -> Counter:
        """
        Returns the instrument for counting operations.

        This property returns the Counter instrument used to count the number of operations made during RPC operations.
        This metric is useful for tracking the frequency of operations and can help identify patterns or issues in the operation flow.

        Returns:
            Counter: The instrument for counting operations.
        """
        return self._instrument_operation_counter

    @property
    def instrument_operation_latency(self) -> Histogram:
        """
        Returns the instrument for measuring operation latency.

        This property returns the Histogram instrument used to measure the latency of operations.
        This metric is useful for tracking the performance of operations and can help identify bottlenecks or issues in the operation flow.

        Returns:
            Histogram: The instrument for measuring operation latency.
        """
        return self._instrument_operation_latency

    def record_attempt_start(self) -> None:
        """
        Records the start of a new attempt within the current operation.

        This method increments the attempt count for the current operation and marks the start of a new attempt.
        It is used to track the number of attempts made during an operation and to identify the start of each attempt for metrics and tracing purposes.
        """
        self.current_op.increment_attempt_count()
        self.current_op.new_attempt()

    def record_attempt_completion(self) -> None:
        """
        Records the completion of an attempt within the current operation.

        This method updates the status of the current attempt to indicate its completion and records the latency of the attempt.
        It calculates the elapsed time since the attempt started and uses this value to record the attempt latency metric.
        This metric is useful for tracking the performance of individual attempts and can help identify bottlenecks or issues in the operation flow.

        If metrics tracing is not enabled, this method does not perform any operations.
        """
        if not self.enabled:
            return
        self.current_op.current_attempt.status = http.client.OK.phrase

        # Build Attributes
        attempt_attributes = self._create_attempt_otel_attributes()

        # Calculate elapsed time
        attempt_latency_ms = self._get_ms_time_diff(
            start=self.current_op.current_attempt.start_time, end=datetime.now()
        )

        # Record attempt latency
        self.instrument_attempt_latency.record(
            amount=attempt_latency_ms, attributes=attempt_attributes
        )

    def record_operation_start(self) -> None:
        """
        Records the start of a new operation.

        This method marks the beginning of a new operation and initializes the operation's metrics tracking.
        It is used to track the start time of an operation, which is essential for calculating operation latency and other metrics.
        If metrics tracing is not enabled, this method does not perform any operations.
        """
        if not self.enabled:
            return
        self.current_op.start()

    def record_operation_completion(self) -> None:
        """
        Records the completion of an operation.

        This method marks the end of an operation and updates the metrics accordingly.
        It calculates the operation latency by measuring the time elapsed since the operation started and records this metric.
        Additionally, it increments the operation count and records the attempt count for the operation.
        If metrics tracing is not enabled, this method does not perform any operations.
        """
        if not self.enabled:
            return
        end_time = datetime.now()

        # Build Attributes
        operation_attributes = self._create_operation_otel_attributes()
        attempt_attributes = self._create_attempt_otel_attributes()

        # Calculate elapsed time
        operation_latency_ms = self._get_ms_time_diff(
            start=self.current_op.start_time, end=end_time
        )

        # Increase operation count
        self.instrument_operation_counter.add(amount=1, attributes=operation_attributes)

        # Record operation latency
        self.instrument_operation_latency.record(
            amount=operation_latency_ms, attributes=operation_attributes
        )

        # Record Attempt Count
        self.instrument_attempt_counter.add(
            self.current_op.attempt_count, attributes=attempt_attributes
        )

    def _create_otel_attributes(self) -> Dict[str, str]:
        """
        Creates a dictionary of attributes for OpenTelemetry metrics tracing.

        This method initializes a copy of the client attributes and adds specific operation attributes
        such as the method name, direct path enabled status, and direct path used status.
        These attributes are used to provide context to the metrics being traced.
        If metrics tracing is not enabled, this method does not perform any operations.
        Returns:
            dict[str, str]: A dictionary of attributes for OpenTelemetry metrics tracing.
        """
        if not self.enabled:
            return

        attributes = self.client_attributes.copy()
        attributes[METRIC_LABEL_KEY_METHOD] = self.method
        attributes[METRIC_LABEL_KEY_DIRECT_PATH_ENABLED] = str(
            self.current_op.direct_path_enabled
        )
        if self.current_op.current_attempt is not None:
            attributes[METRIC_LABEL_KEY_DIRECT_PATH_USED] = str(
                self.current_op.current_attempt.direct_path_used
            )

        return attributes

    def _create_operation_otel_attributes(self) -> Dict[str, str]:
        """
        Creates a dictionary of attributes specific to an operation for OpenTelemetry metrics tracing.

        This method builds upon the base attributes created by `_create_otel_attributes` and adds the operation status.
        These attributes are used to provide context to the metrics being traced for a specific operation.
        If metrics tracing is not enabled, this method does not perform any operations.

        Returns:
            dict[str, str]: A dictionary of attributes specific to an operation for OpenTelemetry metrics tracing.
        """
        if not self.enabled:
            return

        attributes = self._create_otel_attributes()
        attributes[METRIC_LABEL_KEY_STATUS] = self.current_op.status
        return attributes

    def _create_attempt_otel_attributes(self) -> Dict[str, str]:
        """
        Creates a dictionary of attributes specific to an attempt within an operation for OpenTelemetry metrics tracing.

        This method builds upon the operation attributes created by `_create_operation_otel_attributes` and adds the attempt status.
        These attributes are used to provide context to the metrics being traced for a specific attempt within an operation.
        If metrics tracing is not enabled, this method does not perform any operations.
        Returns:
            dict[str, str]: A dictionary of attributes specific to an attempt within an operation for OpenTelemetry metrics tracing.
        """
        if not self.enabled:
            return

        attributes = self._create_operation_otel_attributes()
        # Short circuit out if we don't have an attempt
        if self.current_op.current_attempt is not None:
            attributes[METRIC_LABEL_KEY_STATUS] = self.current_op.current_attempt.status

        return attributes

    @staticmethod
    def _get_ms_time_diff(start: datetime, end: datetime) -> float:
        """
        Calculates the time difference in milliseconds between two datetime objects.

        This method calculates the time difference between two datetime objects and returns the result in milliseconds.
        This is useful for measuring the duration of operations or attempts for metrics tracing.
        Note: total_seconds() returns a float value of seconds.

        Args:
            start (datetime): The start datetime.
            end (datetime): The end datetime.

        Returns:
            float: The time difference in milliseconds.
        """
        time_delta = end - start
        return time_delta.total_seconds() * 1000

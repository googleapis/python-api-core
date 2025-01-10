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

"""Factory for creating MetricTracer instances, facilitating metrics collection and tracing."""

from google.api_core.metrics_tracer import (
    MetricsTracer,
    # Monitored Resource Labels
    MONITORED_RES_LABEL_KEY_PROJECT,
    MONITORED_RES_LABEL_KEY_INSTANCE,
    MONITORED_RES_LABEL_KEY_INSTANCE_CONFIG,
    MONITORED_RES_LABEL_KEY_LOCATION,
    MONITORED_RES_LABEL_KEY_CLIENT_HASH,
    # Metric Labels,
    METRIC_LABEL_KEY_CLIENT_UID,
    METRIC_LABEL_KEY_CLIENT_NAME,
    METRIC_LABEL_KEY_DATABASE,
)
from typing import Dict

try:
    from opentelemetry.metrics import Counter, Histogram, get_meter_provider

    HAS_OPENTELEMETRY_INSTALLED = True
except ImportError:  # pragma: NO COVER
    HAS_OPENTELEMETRY_INSTALLED = False

from google.api_core import version as api_core_version

# Constants
BUILT_IN_METRICS_METER_NAME = "gax-python"


class MetricsTracerFactory:
    """Factory class for creating MetricTracer instances. This class facilitates the creation of MetricTracer objects, which are responsible for collecting and tracing metrics."""

    enabled: bool
    _instrument_attempt_latency: Histogram
    _instrument_attempt_counter: Counter
    _instrument_operation_latency: Histogram
    _instrument_operation_counter: Counter
    _client_attributes: Dict[str, str]

    @property
    def instrument_attempt_latency(self) -> Histogram:
        return self._instrument_attempt_latency

    @property
    def instrument_attempt_counter(self) -> Counter:
        return self._instrument_attempt_counter

    @property
    def instrument_operation_latency(self) -> Histogram:
        return self._instrument_operation_latency

    @property
    def instrument_operation_counter(self) -> Counter:
        return self._instrument_operation_counter

    def __init__(
        self,
        enabled: bool,
        service_name: str,
        project: str,
        instance: str,
        instance_config: str,
        location: str,
        client_hash: str,
        client_uid: str,
        client_name: str,
        database: str,
    ):
        """Initializes a MetricsTracerFactory instance with the given parameters.

        This constructor initializes a MetricsTracerFactory instance with the provided service name, project, instance, instance configuration, location, client hash, client UID, client name, and database. It sets up the necessary metric instruments and client attributes for metrics tracing.

        Args:
            service_name (str): The name of the service for which metrics are being traced.
            project (str): The project ID for the monitored resource.
            instance (str): The instance ID for the monitored resource.
            instance_config (str): The instance configuration for the monitored resource.
            location (str): The location of the monitored resource.
            client_hash (str): A unique hash for the client.
            client_uid (str): The unique identifier for the client.
            client_name (str): The name of the client.
            database (str): The database name associated with the client.
        """
        self.enabled = enabled
        self._create_metric_instruments(service_name)
        self._client_attributes = {
            MONITORED_RES_LABEL_KEY_PROJECT: project,
            MONITORED_RES_LABEL_KEY_INSTANCE: instance,
            MONITORED_RES_LABEL_KEY_INSTANCE_CONFIG: instance_config,
            MONITORED_RES_LABEL_KEY_LOCATION: location,
            MONITORED_RES_LABEL_KEY_CLIENT_HASH: client_hash,
            METRIC_LABEL_KEY_CLIENT_UID: client_uid,
            METRIC_LABEL_KEY_CLIENT_NAME: client_name,
            METRIC_LABEL_KEY_DATABASE: database,
        }

    @property
    def client_attributes(self) -> Dict[str, str]:
        """Returns a dictionary of client attributes used for metrics tracing.

        This property returns a dictionary containing client attributes such as project, instance,
        instance configuration, location, client hash, client UID, client name, and database.
        These attributes are used to provide context to the metrics being traced.

        Returns:
            dict[str, str]: A dictionary of client attributes.
        """
        return self._client_attributes

    def create_metrics_tracer(self, method: str) -> MetricsTracer:
        """Creates and returns a MetricsTracer instance with default settings and client attributes.

        This method initializes a MetricsTracer instance with default settings for metrics tracing,
        with disabled metrics tracing and no direct path enabled by default.
        It also sets the client attributes based on the factory's configuration.

        Args:
            method (str): The name of the method for which metrics are being traced.

        Returns:
            MetricsTracer: A MetricsTracer instance with default settings and client attributes.
        """
        metrics_tracer = MetricsTracer(
            enabled=self.enabled and HAS_OPENTELEMETRY_INSTALLED,
            method=method,
            is_direct_path_enabled=False,  # Direct path is disabled by default
            instrument_attempt_latency=self.instrument_attempt_latency,
            instrument_attempt_counter=self.instrument_attempt_counter,
            instrument_operation_latency=self.instrument_operation_latency,
            instrument_operation_counter=self.instrument_operation_counter,
            client_attributes=self.client_attributes,
        )
        return metrics_tracer

    def _create_metric_instruments(self, service_name: str) -> None:
        """
        Creates and sets up metric instruments for the given service name.

        This method initializes and configures metric instruments for attempt latency, attempt counter,
        operation latency, and operation counter. These instruments are used to measure and track
        metrics related to attempts and operations within the service.

        Args:
            service_name (str): The name of the service for which metric instruments are being created.
        """
        if not HAS_OPENTELEMETRY_INSTALLED:  # pragma: NO COVER
            return

        meter_provider = get_meter_provider()
        meter = meter_provider.get_meter(
            name=BUILT_IN_METRICS_METER_NAME, version=api_core_version
        )

        self._instrument_attempt_latency = meter.create_histogram(
            name=f"{service_name}/attempt_latency",
            unit="ms",
            description="Time an individual attempt took.",
        )

        self._instrument_attempt_counter = meter.create_counter(
            name=f"{service_name}/attempt_count",
            unit="1",
            description="Number of attempts.",
        )

        self._instrument_operation_latency = meter.create_histogram(
            name=f"{service_name}/operation_latency",
            unit="ms",
            description="Total time until final operation success or failure, including retries and backoff.",
        )

        self._instrument_operation_counter = meter.create_counter(
            name=f"{service_name}/operation_count",
            unit="1",
            description="Number of operations.",
        )

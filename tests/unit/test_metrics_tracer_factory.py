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
from google.api_core.metrics_tracer_factory import MetricsTracerFactory
from google.api_core.metrics_tracer import MetricsTracer


@pytest.fixture
def metrics_tracer_factory():
    return MetricsTracerFactory(
        enabled=True,
        service_name="test_service",
        project="test_project",
        instance="test_instance",
        instance_config="test_config",
        location="test_location",
        client_hash="test_hash",
        client_uid="test_uid",
        client_name="test_name",
        database="test_db",
    )


def test_initialization(metrics_tracer_factory):
    assert metrics_tracer_factory.enabled is True
    assert metrics_tracer_factory.client_attributes["project_id"] == "test_project"


def test_create_metrics_tracer(metrics_tracer_factory):
    tracer = metrics_tracer_factory.create_metrics_tracer("test_method")
    assert isinstance(tracer, MetricsTracer)
    assert tracer.method == "test_method"
    assert tracer.enabled is True


def test_client_attributes(metrics_tracer_factory):
    attributes = metrics_tracer_factory.client_attributes
    assert attributes["project_id"] == "test_project"
    assert attributes["instance_id"] == "test_instance"

from enum import Enum
from typing import Dict

from prometheus_client import start_http_server
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics._internal.instrument import (
    Counter,
    Histogram,
    Gauge,
)
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from ..env import LOG


class CounterMetricName(Enum):
    """Enum for all available metrics."""

    REQUEST = "requests_total"
    HEALTHCHECK = "healthcheck_total"
    LLM_INVOCATIONS = "llm_invocations_total"
    LLM_TOKENS_INPUT = "llm_tokens_input_total"
    LLM_TOKENS_OUTPUT = "llm_tokens_output_total"

    def get_description(self) -> str:
        """Get the description for this metric."""
        descriptions = {
            CounterMetricName.REQUEST: "Total number of requests to the memobase server",
            CounterMetricName.HEALTHCHECK: "Total number of healthcheck requests to the memobase server",
            CounterMetricName.LLM_INVOCATIONS: "Total number of LLM invocations",
            CounterMetricName.LLM_TOKENS_INPUT: "Total number of input tokens",
            CounterMetricName.LLM_TOKENS_OUTPUT: "Total number of output tokens",
        }
        return descriptions[self]

    def get_metric_name(self) -> str:
        """Get the full metric name with prefix."""
        return f"memobase_server_{self.value}"


class HistogramMetricName(Enum):
    """Enum for histogram metrics."""

    LLM_LATENCY_MS = "llm_latency"
    REQUEST_LATENCY_MS = "request_latency"

    def get_description(self) -> str:
        """Get the description for this metric."""
        descriptions = {
            HistogramMetricName.LLM_LATENCY_MS: "Latency of the LLM in milliseconds",
            HistogramMetricName.REQUEST_LATENCY_MS: "Latency of the request in milliseconds",
        }
        return descriptions[self]

    def get_metric_name(self) -> str:
        """Get the full metric name with prefix."""
        return f"memobase_server_{self.value}"


class GaugeMetricName(Enum):
    """Enum for gauge metrics."""

    INPUT_TOKEN_COUNT = "input_token_count_per_call"
    OUTPUT_TOKEN_COUNT = "output_token_count_per_call"

    def get_description(self) -> str:
        """Get the description for this metric."""
        descriptions = {
            GaugeMetricName.INPUT_TOKEN_COUNT: "Number of input tokens per call",
            GaugeMetricName.OUTPUT_TOKEN_COUNT: "Number of output tokens per call",
        }
        return descriptions[self]

    def get_metric_name(self) -> str:
        """Get the full metric name with prefix."""
        return f"memobase_server_{self.value}"


class TelemetryManager:
    """Manages telemetry setup and metrics for the memobase server."""

    def __init__(
        self, service_name: str = "memobase-server", prometheus_port: int = 9464
    ):
        self.service_name = service_name
        self.prometheus_port = prometheus_port
        self.metrics: Dict[
            CounterMetricName | HistogramMetricName | GaugeMetricName,
            Counter | Histogram | Gauge,
        ] = {}
        self._meter = None

    def setup_telemetry(self) -> None:
        """Initialize OpenTelemetry with Prometheus exporter."""
        resource = Resource(attributes={SERVICE_NAME: self.service_name})
        reader = PrometheusMetricReader()
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)

        # Start Prometheus HTTP server, skip if port is already in use
        try:
            start_http_server(self.prometheus_port)
        except OSError as e:
            if e.errno == 48:  # Address already in use
                LOG.warning(
                    f"Prometheus HTTP server already running on port {self.prometheus_port}"
                )
            else:
                raise e

        # Initialize meter
        self._meter = metrics.get_meter(self.service_name)

    def setup_metrics(self) -> None:
        """Initialize all metrics."""
        if not self._meter:
            raise RuntimeError("Call setup_telemetry() before setup_metrics()")

        # Create counters
        for metric in CounterMetricName:
            self.metrics[metric] = self._meter.create_counter(
                metric.get_metric_name(),
                unit="1",
                description=metric.get_description(),
            )

        # Create histogram for latency
        for metric in HistogramMetricName:
            self.metrics[metric] = self._meter.create_histogram(
                metric.get_metric_name(),
                unit="ms",
                description=metric.get_description(),
            )

        # Create gauges for token counts
        for metric in GaugeMetricName:
            self.metrics[metric] = self._meter.create_gauge(
                metric.get_metric_name(),
                unit="1",
                description=metric.get_description(),
            )

    def increment_counter_metric(
        self,
        metric: CounterMetricName,
        value: int = 1,
        attributes: Dict[str, str] = None,
    ) -> None:
        """Increment a counter metric."""
        if metric not in self.metrics:
            raise KeyError(f"Metric {metric} not initialized")
        self.metrics[metric].add(value, attributes)

    def record_histogram_metric(
        self,
        metric: HistogramMetricName,
        value: float,
        attributes: Dict[str, str] = None,
    ) -> None:
        """Record a histogram metric value."""
        if metric not in self.metrics:
            raise KeyError(f"Metric {metric} not initialized")
        self.metrics[metric].record(value, attributes)

    def set_gauge_metric(
        self,
        metric: GaugeMetricName,
        value: float,
        attributes: Dict[str, str] = None,
    ) -> None:
        """Set a gauge metric."""
        if metric not in self.metrics:
            raise KeyError(f"Metric {metric} not initialized")
        self.metrics[metric].set(value, attributes)


# Create a global instance
telemetry_manager = TelemetryManager()
telemetry_manager.setup_telemetry()
telemetry_manager.setup_metrics()

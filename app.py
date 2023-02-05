#!/usr/bin/env python

import os
from typing import Any

from flask import Flask, request
from main import handleHttp
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import (
    CloudTraceFormatPropagator,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor,  BatchSpanProcessor,  ConsoleSpanExporter
from opentelemetry.instrumentation.grpc import GrpcInstrumentorClient
from opentelemetry.instrumentation.requests import RequestsInstrumentor


try:
    import googleclouddebugger
    googleclouddebugger.enable(
            breakpoint_enable_canary=False)
except ImportError:
    pass

TRACE_EXPORTER = os.environ.get("TRACE_EXPORTER", "").lower()
TRACE_PROPAGATE = os.environ.get("TRACE_PROPAGATE", "").lower()


resource = Resource.create({"service.name": "filter-feed"})
tracer_provider = TracerProvider(resource=resource)

RequestsInstrumentor().instrument()

grpc_client_instrumentor = GrpcInstrumentorClient()
grpc_client_instrumentor.instrument()

if TRACE_PROPAGATE == "google":
    set_global_textmap(CloudTraceFormatPropagator())

if TRACE_EXPORTER == "stackdriver":
    tracer_provider.add_span_processor(SimpleSpanProcessor(CloudTraceSpanExporter()))
elif TRACE_EXPORTER == "stdout":
    tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

trace.set_tracer_provider(tracer_provider)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

@app.route('/v1/<int:key>')
def entry(key):
    return handleHttp(request, key)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

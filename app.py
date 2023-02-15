#!/usr/bin/env python

import os
from typing import Any
import json
import logging as py_logging
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, request
import werkzeug.exceptions
from absl import logging
import google.cloud.error_reporting
import google.cloud.logging
import google.cloud.logging.handlers
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import CloudTraceFormatPropagator
from opentelemetry.sdk.resources import Resource,  get_aggregated_resources
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor,  ConsoleSpanExporter
from opentelemetry.instrumentation.grpc import GrpcInstrumentorClient
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.resourcedetector.gcp_resource_detector import GoogleCloudResourceDetector

import filter_feed
import view

TRACE_EXPORTER = os.environ.get("TRACE_EXPORTER", "").lower()
TRACE_PROPAGATE = os.environ.get("TRACE_PROPAGATE", "").lower()
STACKDRIVER_ERROR_REPORTING = os.environ.get("STACKDRIVER_ERROR_REPORTING", "").lower() in (1, 'true', 't')
LOG_HANDLER = os.environ.get("LOG_HANDLER", "").lower()
PROJECT_ID = os.environ.get("PROJECT_ID", "filter-feed")

resource = Resource.create({"service.name": PROJECT_ID})
if TRACE_EXPORTER:
    # slow, don't bother if we're not using it
    resource.merge(get_aggregated_resources([GoogleCloudResourceDetector()]))
tracer_provider = TracerProvider(resource=resource)

if TRACE_EXPORTER != "stackdriver":
    # If you instrument requests while using CloudTraceSpanExporter in SimpleSpanProcessor mode you get a loop
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

if LOG_HANDLER == 'absl':
    logging.use_absl_handler()
elif LOG_HANDLER == "stackdriver":
    client = google.cloud.logging.Client()
    handler = google.cloud.logging.handlers.CloudLoggingHandler(client)
    google.cloud.logging.handlers.setup_logging(handler)
elif LOG_HANDLER == 'structured':
    class StructureLogFormater(py_logging.Formatter):
        def format(self, record):
            span_context = trace.get_current_span().get_span_context()
            structured = {
                "message": super().format(record),
                "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                "severity": record.levelname,
                "logging.googleapis.com/sourceLocation": {
                    "file": record.filename,
                    "line": record.lineno,
                    "function": record.funcName
                }
            }
            if span_context.trace_id:
                structured["logging.googleapis.com/trace"] =  f"projects/{PROJECT_ID}/traces/{span_context.trace_id:x}"
            if span_context.span_id:
                structured["logging.googleapis.com/spanId"] =  f"{span_context.span_id:x}"
            return json.dumps(structured)
    handler = py_logging.StreamHandler()
    handler.setFormatter(StructureLogFormater())
    py_logging.getLogger().addHandler(handler)

if "LOG_LEVEL" in os.environ:
    log_level = os.environ["LOG_LEVEL"].upper()
    logging.set_verbosity(log_level)
    requests_log = py_logging.getLogger("urllib3")
    requests_log.setLevel(log_level)
    requests_log.propagate = True
    flask_log = py_logging.getLogger("app")
    flask_log.setLevel(log_level)


app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

def error_reporting(f):
    client = google.cloud.error_reporting.Client(project=PROJECT_ID)
    @wraps(f)
    def wrapped(*args,  **kwargs):
        try:
            return f(*args,  **kwargs)
        except werkzeug.exceptions.NotFound as e:
            raise
        except Exception as e:
            logging.exception(e)
            if STACKDRIVER_ERROR_REPORTING:
                try:
                    client.report_exception(
                        http_context=google.cloud.error_reporting.build_flask_context(request))
                except Exception:
                    logging.exception("Failed to send error report to Google")
            raise
    return wrapped

@app.route('/v1/<int:key>.rss')
@app.route('/v1/<int:key>.atom')
@app.route('/v1/<int:key>.xml')
@app.route('/v1/<int:key>')
@error_reporting
def entry(key):
        return filter_feed.handleHttp(request, key)

@app.route('/v1')
@app.route('/v1/')
@app.route('/')
@error_reporting
def  list_feeds():
    return view.list_feeds(request)

@app.get('/v1/<int:key>/edit')
@error_reporting
def  get_feed(key):
    return view.get_feed(request,  key)

@app.post('/v1/<int:key>/edit')
@error_reporting
def  update_feed(key):
    return view.update_feed(request,  key)

@app.post('/v1/<int:key>/delete')
@error_reporting
def  delete_feed(key):
    return view.delete_feed(request,  key)

@app.get('/v1/create')
@error_reporting
def  create_feed_form():
    return view.create_feed_form(request)

@app.post('/v1/create')
@error_reporting
def  create_feed():
    return view.create_feed(request)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

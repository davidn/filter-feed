#!/usr/bin/env python

import os
from typing import Any, Union
import json
import logging as py_logging
from datetime import datetime, timezone
from functools import wraps

import click
from flask import Flask, request
from flask_security import Security, login_required
from flask_cloud_ndb import CloudNDB
import werkzeug.exceptions
from absl import logging
import google.cloud.error_reporting
import google.cloud.logging
import google.cloud.logging.handlers
from google.cloud import ndb

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
import model
import ndb_user_datastore
import flask
from flask_security.utils import uia_email_mapper
from google.cloud.ndb.context import get_toplevel_context
from werkzeug.routing.converters import BaseConverter, ValidationError

TRACE_EXPORTER = os.environ.get("TRACE_EXPORTER", "").lower()
TRACE_PROPAGATE = os.environ.get("TRACE_PROPAGATE", "").lower()
STACKDRIVER_ERROR_REPORTING = os.environ.get("STACKDRIVER_ERROR_REPORTING", "").lower() in (1, 'true', 't')
LOG_HANDLER = os.environ.get("LOG_HANDLER", "").lower()
PROJECT_ID = os.environ.get("PROJECT_ID", "filter-feed")
SECRET_KEY = os.environ.get('SECRET_KEY', "secret key only for DEBUG")
SECURITY_PASSWORD_SALT = os.environ.get("SECURITY_PASSWORD_SALT", '257726044742079860569628914655245968662')

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
app.config['SECRET_KEY'] = SECRET_KEY
#only for debug!
app.config['SECURITY_PASSWORD_SALT'] = SECURITY_PASSWORD_SALT
app.config['SECURITY_USER_IDENTITY_ATTRIBUTES'] = [
    {"email": {"mapper": uia_email_mapper, "case_insensitive": False}},
]
app.config["NDB_PROJECT"] = PROJECT_ID

cloud_ndb = CloudNDB(app)
user_datastore = ndb_user_datastore.NdbUserDatastore(model.User, model.Role)
app.security = Security(app, user_datastore)

# hack to add NDB context for flask CLI
original_invoke = click.Context.invoke
@wraps(click.Context.invoke)
def wrapped_invoke(*args, **kwargs):
    if get_toplevel_context(raise_context_error=False) is None:
        with cloud_ndb.context():
            return original_invoke(*args, **kwargs)
    else:
        return original_invoke(*args, **kwargs)
click.Context.invoke = wrapped_invoke

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

# flask testing calls converters outside of wsgi_app, and thus outside of the
# ndb context, so we can't reliably call ndb.Key. Therefore this converter just
# outputs the constructor for an ndb key, which is instantiated in the routes.
KeyConstructor = Union[tuple[str, int], tuple[str, int, str, int]]
class KeyConverter(BaseConverter):
    regex = r"\d+(/\d+)?"
    part_isolating = False
    def to_python(self, value: str) -> KeyConstructor:
        ids = value.split("/")
        try:
            ids = [int(id) for id in ids]
        except ValueError:
            raise ValidationError()
        if len(ids) == 1:
            return ("FilterFeed", ids[0])
        elif len(ids) == 2:
            return ("User", ids[0], "FilterFeed", ids[1])
        else:
            raise ValidationError()
    def to_url(self, value: Union[ndb.Key, KeyConstructor]) -> str:
        if isinstance(value, ndb.Key):
            return "/".join(str(pair[1]) for pair in value.pairs())
        else:
            return "/".join(str(x) for x in value[1::2])
app.url_map.converters['key'] = KeyConverter


@app.route('/v1/<key:key>.rss')
@app.route('/v1/<key:key>.atom')
@app.route('/v1/<key:key>.xml')
@app.route('/v1/<key:key>')
@error_reporting
def feed_by_key(key: KeyConstructor):
    key = ndb.Key(*key)
    with model.ApplyFilterPermission(key).require(403):
        return filter_feed.feed_by_key(request, key)

@app.route('/v1/')
@app.route('/')
@login_required
@error_reporting
def  list_feeds():
    return view.list_feeds(request)

@app.get('/v1/<key:key>/edit')
@login_required
@error_reporting
def  get_feed(key: KeyConstructor):
    key = ndb.Key(*key)
    with model.ViewFilterPermission(key).require(403):
        return view.get_feed(request,  key)

@app.post('/v1/<key:key>/edit')
@login_required
@error_reporting
def  update_feed(key: KeyConstructor):
    key = ndb.Key(*key)
    with model.EditFilterPermission(key).require(403):
        return view.update_feed(request,  key)

@app.post('/v1/<key:key>/delete')
@login_required
@error_reporting
def  delete_feed(key: KeyConstructor):
    key = ndb.Key(*key)
    with model.DeleteFilterPermission(key).require(403):
        return view.delete_feed(request,  key)

@app.route('/v1/create', methods=['GET', 'POST'])
@login_required
@error_reporting
def  create_feed():
    return view.create_feed(request)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

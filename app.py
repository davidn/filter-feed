#!/usr/bin/env python

import os
import logging

from flask import Flask, request
from main import handleHttp
from opencensus.common.transports.async_ import AsyncTransport
from opencensus.ext.flask.flask_middleware import FlaskMiddleware
from opencensus.trace import (
    samplers, print_exporter, logging_exporter)
from opencensus.trace.propagation import (
    google_cloud_format, trace_context_http_header_format)
from opencensus.ext.stackdriver import trace_exporter

try:
    import googleclouddebugger
    googleclouddebugger.enable(
            breakpoint_enable_canary=False)
except ImportError:
    pass

TRACE_EXPORTER = os.environ.get("TRACE_EXPORTER", "").lower()
TRACE_PROPAGATE = os.environ.get("TRACE_PROPAGATE", "").lower()

if TRACE_PROPAGATE == "google":
    propagator = google_cloud_format.GoogleCloudFormatPropagator()
else:
    propagator = trace_context_http_header_format.TraceContextPropagator()
if TRACE_EXPORTER == "stackdriver":
    exporter = trace_exporter.StackdriverExporter(transport=AsyncTransport)
    sampler = samplers.AlwaysOnSampler()
elif TRACE_EXPORTER == "log":
    exporter = logging_exporter.LoggingExporter(
        handler=logging.NullHandler(), transport=AsyncTransport)
    sampler = samplers.AlwaysOnSampler()
elif TRACE_EXPORTER == "stdout":
    exporter = print_exporter.PrintExporter(transport=AsyncTransport)
    sampler = samplers.AlwaysOnSampler()
else:
    exporter = print_exporter.PrintExporter(transport=AsyncTransport)
    sampler = samplers.AlwaysOffSampler()


app = Flask(__name__)
app.config['OPENCENSUS'] = {
    'TRACE': {
        'PROPAGATOR': propagator,
        'EXPORTER': exporter,
        'SAMPLER': sampler
    }
}
FlaskMiddleware(app)

@app.route('/v1/<int:key>')
def entry(key):
    return handleHttp(request, key)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

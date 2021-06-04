#!/usr/bin/env python3

import os
import json
import logging as py_logging
from datetime import datetime, timezone

from absl import logging
from google.cloud import error_reporting
import google.cloud.logging
import google.cloud.logging.handlers
import requests
from typing import Sequence, Optional, TYPE_CHECKING
from opencensus.common.transports.async_ import AsyncTransport
from opencensus.trace import (
    config_integration, tracer, samplers, execution_context, print_exporter, logging_exporter)
from opencensus.trace.propagation import (
    google_cloud_format, trace_context_http_header_format)
from opencensus.ext.stackdriver import trace_exporter
import xml.etree.ElementTree as ET
import flask


STACKDRIVER_ERROR_REPORTING = os.environ.get("STACKDRIVER_ERROR_REPORTING", "").lower() in (1, 'true', 't')
TRACE_EXPORTER = os.environ.get("TRACE_EXPORTER", "").lower()
TRACE_PROPAGATE = os.environ.get("TRACE_PROPAGATE", "").lower()
LOG_HANDLER = os.environ.get("LOG_HANDLER", "").lower()
PROJECT_ID = os.environ.get("PROJECT_ID", "")

config_integration.trace_integrations(['requests', 'logging'])

if LOG_HANDLER == 'absl':
    logging.use_absl_handler()
elif LOG_HANDLER == "stackdriver":
    client = google.cloud.logging.Client()
    handler = google.cloud.logging.handlers.CloudLoggingHandler(client)
    google.cloud.logging.handlers.setup_logging(handler)
elif LOG_HANDLER == 'structured':
    class StructureLogFormater(py_logging.Formatter):
        def format(self, record):
            context = execution_context.get_opencensus_tracer().span_context
            structured = {
                "message": super().format(record),
                "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                "severity": record.levelname,
                "logging.googleapis.com/trace": f"projects/{PROJECT_ID}/traces/{context.trace_id}",
                "logging.googleapis.com/spanId": context.span_id,
                "logging.googleapis.com/sourceLocation": {
                    "file": record.filename,
                    "line": record.lineno,
                    "function": record.funcName
                }
            }
            if context.span_id:
                structured["logging.googleapis.com/spanId"] = context.span_id
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

def initialize_tracer(request: 'flask.Request') -> tracer.Tracer:
    if TRACE_PROPAGATE == "google":
        propagator = google_cloud_format.GoogleCloudFormatPropagator()
    else:
        propagator = trace_context_http_header_format.TraceContextPropagator()
    if TRACE_EXPORTER == "stackdriver":
        exporter = trace_exporter.StackdriverExporter(transport=AsyncTransport)
        sampler = samplers.AlwaysOnSampler()
    elif TRACE_EXPORTER == "log":
        exporter = logging_exporter.LoggingExporter(
            handler=py_logging.NullHandler(), transport=AsyncTransport)
        sampler = samplers.AlwaysOnSampler()
    elif TRACE_EXPORTER == "stdout":
        exporter = print_exporter.PrintExporter(transport=AsyncTransport)
        sampler = samplers.AlwaysOnSampler()
    else:
        exporter = print_exporter.PrintExporter(transport=AsyncTransport)
        sampler = samplers.AlwaysOffSampler()
    span_context = propagator.from_headers(request.headers)
    return tracer.Tracer(exporter=exporter, sampler=sampler,
                         propagator=propagator, span_context=span_context)



FEED_URL = "https://feeds.megaphone.fm/stuffyoushouldknow"

def modifyRss(root: ET.Element):
    tracer = execution_context.get_opencensus_tracer()
    title = root.find(".//channel/title")
    if title is None:
        logging.warning("Could not find .//channel/title to modify")
    else:
        title.text += " (filtered)"
    with tracer.span(name='filter_rss'):
        chan = root.find("channel")
        if chan is None:
            raise Exception('Missing channel element')
        for item in root.iterfind(".//item"):
            item_title = item.find("title")
            if item_title is not None and "SYSK Selects" in item_title.text:
                chan.remove(item)

def modifyAtom(root: ET.Element):
    tracer = execution_context.get_opencensus_tracer()
    title = root.find(".//feed/title")
    if title is None:
        logging.warning("Could not find .//feed/title to modify")
    else:
        title.text += " (filtered)"
    with tracer.span(name='filter_atom'):
        for entry in root.iterfind(".//entry"):
            entry_title = entry.find("title")
            if entry_title is not None and "SYSK Selects" in entry_title.text:
                root.remove(entry)

def detectRss(content_type: str, root: ET.Element) -> bool:
    if content_type in (
            "application/rss+xml",
            ):
        return True
    return root.tag == "rss"

def detectAtom(content_type: str, root: ET.Element) -> bool:
    if content_type in (
            "application/atom+xml",
            ):
        return True
    return root.tag == "feed"


def handleHttp(request: flask.Request) -> flask.Response:
    res = flask.Response()
    tracer = initialize_tracer(request)
    try:
        upstream = requests.get(FEED_URL)
        with tracer.span(name='parse'):
            root = ET.fromstring(upstream.text)
        if detectRss(upstream.headers['Content-Type'], root):
            modifyRss(root)
        elif detectAtom(upstream.headers['Content-Type'], root):
            modifyAtom(root)
        else:
            logging.error('Could not detect content-type, returning XML unmodified')
        with tracer.span(name='serialize'):
            res.set_data(ET.tostring(root, encoding='unicode') )
            res.content_type = upstream.headers['Content-Type']
    except Exception as e:
        logging.exception(e)
        if STACKDRIVER_ERROR_REPORTING:
            try:
                client = error_reporting.Client()
                client.report_exception(
                    http_context=error_reporting.build_flask_context(request))
            except Exception:
                logging.exception("Failed to send error report to Google")
    return res

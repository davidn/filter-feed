#!/usr/bin/env python3

import filter_feed

import os
import json
import logging as py_logging
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from email.utils import parsedate_to_datetime

from absl import logging
import google.cloud.error_reporting
import google.cloud.logging
import google.cloud.logging.handlers
from google.cloud import ndb
import requests
from typing import Optional, Callable, TypeVar
from opentelemetry import  trace
import xml.etree.ElementTree as ET
import flask
from jqqb_evaluator.evaluator import Evaluator

STACKDRIVER_ERROR_REPORTING = os.environ.get("STACKDRIVER_ERROR_REPORTING", "").lower() in (1, 'true', 't')
LOG_HANDLER = os.environ.get("LOG_HANDLER", "").lower()
PROJECT_ID = os.environ.get("PROJECT_ID", "")

tracer = trace.get_tracer(__name__)

if LOG_HANDLER == 'absl':
    logging.use_absl_handler()
elif LOG_HANDLER == "stackdriver":
    client = google.cloud.logging.Client()
    handler = google.cloud.logging.handlers.CloudLoggingHandler(client)
    google.cloud.logging.handlers.setup_logging(handler)
elif LOG_HANDLER == 'structured':
    class StructureLogFormater(py_logging.Formatter):
        def format(self, record):
            span = trace.get_current_span()
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
            if hasattr(span,  "trace_id"):
                structured["logging.googleapis.com/trace"] =  f"projects/{PROJECT_ID}/traces/{span.trace_id}"
            if hasattr(span,  "span_id"):
                structured["logging.googleapis.com/spanId"] =  span.span_id
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

class NamespaceRecordingTreeBuilder(ET.TreeBuilder):
    def __init__(self, *args,  **kwargs):
        self.ns = {}
        super().__init__(*args,  **kwargs)
    
    def start_ns(self,  prefix,  uri):
        self.ns[prefix] = uri

@dataclass
class Item:
    title: Optional[str]
    date: Optional[datetime]
    description: Optional[str]
    T = TypeVar('T')

    @classmethod
    def _content(cls, item: ET.Element, tag: str, c: Callable[[str], T]=str) -> Optional[T]:
        el = item.find(tag)
        return None if el is None else c(el.text)

    @classmethod
    def fromRssItem(cls, item: ET.Element) -> 'Item':
        return Item(
                title=cls._content(item, "title"),
                date=cls._content(item, "pubDate", parsedate_to_datetime),
                description=cls._content(item, "description")
                )

    @classmethod
    def fromAtomEntry(cls, item: ET.Element) -> 'Item':
        return Item(
                title=cls._content(item, "{http://www.w3.org/2005/Atom}title"),
                date=cls._content(item, "{http://www.w3.org/2005/Atom}updated", datetime.fromisoformat),
                description=cls._content(item, "{http://www.w3.org/2005/Atom}summary")
                )


def modifyRss(root: ET.Element, settings: filter_feed.FilterFeed):
    title = root.find(".//channel/title")
    if title is None:
        logging.warning("Could not find .//channel/title to modify")
    else:
        title.text += " (filtered)"
    with tracer.start_as_current_span('filter_rss'):
        chan = root.find("channel")
        if chan is None:
            raise Exception('Missing channel element')
        evaluator = Evaluator(settings.query_builder)
        delete_items = filter(
                lambda i: evaluator.object_matches_rules(asdict(Item.fromRssItem(i))),
                root.iterfind(".//item"))
        for item in delete_items:
            chan.remove(item)


def modifyAtom(root: ET.Element, settings: filter_feed.FilterFeed):
    title = root.find("./{http://www.w3.org/2005/Atom}title")
    if title is None:
        logging.warning("Could not find ./{http://www.w3.org/2005/Atom}title to modify")
    else:
        title.text += " (filtered)"
    with tracer.start_as_current_span('filter_atom'):
        evaluator = Evaluator(settings.query_builder)
        delete_entries = filter(
                lambda i: evaluator.object_matches_rules(asdict(Item.fromAtomEntry(i))),
                root.iterfind(".//{http://www.w3.org/2005/Atom}entry"))
        for entry in delete_entries:
            root.remove(entry)

def detectRss(content_type: str, root: ET.Element) -> bool:
    if content_type in (
            "application/rss+xml",
            ):
        return True
    return root.tag in "rss"

def detectAtom(content_type: str, root: ET.Element) -> bool:
    if content_type in (
            "application/atom+xml",
            ):
        return True
    return root.tag in ("feed", "{http://www.w3.org/2005/Atom}feed")


def handleHttp(request: flask.Request, key: int) -> flask.Response:
    res = flask.Response()
    try:
        client = ndb.Client()
        with client.context():
            settings = filter_feed.FilterFeed.get_by_id(key)
        if settings is None:
            flask.abort(404)
        upstream = requests.get(settings.url)
        with tracer.start_as_current_span('parse'):
            tb = NamespaceRecordingTreeBuilder()
            root = ET.fromstring(upstream.text,  parser=ET.XMLParser(target=tb))
        if detectRss(upstream.headers.get('Content-Type', None), root):
            modifyRss(root, settings)
        elif detectAtom(upstream.headers.get('Content-Type', None), root):
            modifyAtom(root, settings)
        else:
            logging.error('Could not detect content-type, returning XML unmodified')
        with tracer.start_as_current_span('serialize'):
            nsmap = ET._namespace_map.copy()
            for prefix,  uri in tb.ns.items():
                ET.register_namespace(prefix,  uri)
            res.set_data(ET.tostring(root, encoding='unicode') )
            ET._namespace_map.clear()
            ET._namespace_map.update(nsmap)
            res.content_type = upstream.headers.get('Content-Type', None)
    except Exception as e:
        logging.exception(e)
        if STACKDRIVER_ERROR_REPORTING:
            try:
                client = google.cloud.error_reporting.Client()
                client.report_exception(
                    http_context=google.cloud.error_reporting.build_flask_context(request))
            except Exception:
                logging.exception("Failed to send error report to Google")
        raise
    return res

#!/usr/bin/env python3

import filter_feed

import os
import json
import logging as py_logging
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from email.utils import parsedate_to_datetime

from absl import logging
from google.cloud import error_reporting
import google.cloud.logging
import google.cloud.logging.handlers
from google.cloud import ndb  # type: Any
import requests
from typing import Any, Sequence, Optional, Callable, TypeVar
from opencensus.trace import config_integration, execution_context
import xml.etree.ElementTree as ET
import flask
from jqqb_evaluator.evaluator import Evaluator


STACKDRIVER_ERROR_REPORTING = os.environ.get("STACKDRIVER_ERROR_REPORTING", "").lower() in (1, 'true', 't')
LOG_HANDLER = os.environ.get("LOG_HANDLER", "").lower()
PROJECT_ID = os.environ.get("PROJECT_ID", "")

config_integration.trace_integrations(['logging', 'google_cloud_clientlibs'])

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


# Sadly ElementTree namespace registry is global. Lets just do some common namespaces
ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')
ET.register_namespace('itunes', 'http://www.itunes.com/dtds/podcast-1.0.dtd')
ET.register_namespace('googleplay', 'http://www.google.com/schemas/play-podcasts/1.0')
ET.register_namespace('media', 'http://search.yahoo.com/mrss/')
ET.register_namespace('content', 'http://purl.org/rss/1.0/modules/content/')


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
                title=cls._content(item, "title"),
                date=cls._content(item, "updated", datetime.fromisoformat),
                description=cls._content(item, "summary")
                )


def modifyRss(root: ET.Element, settings: filter_feed.FilterFeed):
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
        evaluator = Evaluator(settings.query_builder)
        delete_items = filter(
                lambda i: evaluator.object_matches_rules(asdict(Item.fromRssItem(i))),
                root.iterfind(".//item"))
        for item in delete_items:
            chan.remove(item)


def modifyAtom(root: ET.Element, settings: filter_feed.FilterFeed):
    tracer = execution_context.get_opencensus_tracer()
    title = root.find(".//feed/title")
    if title is None:
        logging.warning("Could not find .//feed/title to modify")
    else:
        title.text += " (filtered)"
    with tracer.span(name='filter_atom'):
        evaluator = Evaluator(settings.query_builder)
        delete_entries = filter(
                lambda i: evaluator.object_matches_rules(asdict(Item.fromAtomEntry(i))),
                root.iterfind(".//entry"))
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


def handleHttp(request: flask.Request, key: str) -> flask.Response:
    tracer = execution_context.get_opencensus_tracer()
    res = flask.Response()
    try:
        client = ndb.Client()
        with client.context():
            settings = filter_feed.FilterFeed.get_by_id(int(key))
        upstream = requests.get(settings.url)
        with tracer.span(name='parse'):
            root = ET.fromstring(upstream.text)
        if detectRss(upstream.headers.get('Content-Type', None), root):
            modifyRss(root, settings)
        elif detectAtom(upstream.headers.get('Content-Type', None), root):
            modifyAtom(root, settings)
        else:
            logging.error('Could not detect content-type, returning XML unmodified')
        with tracer.span(name='serialize'):
            res.set_data(ET.tostring(root, encoding='unicode') )
            res.content_type = upstream.headers.get('Content-Type', None)
    except Exception as e:
        logging.exception(e)
        if STACKDRIVER_ERROR_REPORTING:
            try:
                client = error_reporting.Client()
                client.report_exception(
                    http_context=error_reporting.build_flask_context(request))
            except Exception:
                logging.exception("Failed to send error report to Google")
        raise
    return res

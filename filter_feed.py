#!/usr/bin/env python3


from dataclasses import asdict
from typing import Any
import xml.etree.ElementTree as ET

from absl import logging
import flask
import requests
from google.cloud import ndb  # type: Any
from opentelemetry import  trace
from jqqb_evaluator.evaluator import Evaluator

import model
from item import Item

tracer = trace.get_tracer(__name__)

class NamespaceRecordingTreeBuilder(ET.TreeBuilder):
    def __init__(self, *args,  **kwargs):
        self.ns = {}
        super().__init__(*args,  **kwargs)
    
    def start_ns(self,  prefix,  uri):
        self.ns[prefix] = uri


def modifyRss(root: ET.Element, settings: model.FilterFeed):
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


def modifyAtom(root: ET.Element, settings: model.FilterFeed):
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
    client = ndb.Client()
    with client.context():
        settings = model.FilterFeed.get_by_id(key)
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
        # pytype: disable=module-attr
        nsmap = ET._namespace_map.copy()
        for prefix,  uri in tb.ns.items():
            ET.register_namespace(prefix,  uri)
        res.set_data(ET.tostring(root, encoding='unicode') )
        ET._namespace_map.clear()
        ET._namespace_map.update(nsmap)
        # pytype: enable=module-attr
        res.content_type = upstream.headers.get('Content-Type', None)
    return res

#!/usr/bin/env python3

import json
from datetime import datetime

from google.cloud import ndb
from absl import app, flags
from validators import url
from jqqb_evaluator.evaluator import Evaluator

from filter_feed import FilterFeed

flags.DEFINE_integer("id", None, "ID for previous feed")
flags.DEFINE_string("url", None, "Upstream feed")
flags.DEFINE_string("query_builder", None, "querybuilder string to filter")

@flags.validator('url', 'not a valid url')
def _CheckUrl(value) -> bool:
    if value is None:
        return True
    return url(value, public=True)

@flags.validator('query_builder', 'Not a valid query builder')
def _CheckQuery(value):
    if value is None:
        return True
    e = Evaluator(value)
    try:
        e.object_matches_rules({"title": "blah", "pubdate": datetime.min, "description": "desc"})
    except:
        return False
    return True

@flags.multi_flags_validator(["id", "url", "query_builder"],
        "Require both --url and --query_builder to create a new feed.")
def _CheckFlagsSet(f) -> bool:
    # If no id is set (new feed) we need both fields
    if not f["id"]:
        return bool(f["url"] and f["query_builder"])
    return True

FLAGS = flags.FLAGS

def upsert_feed(feed_id, url, query_builder) -> str:
    client = ndb.Client()
    with client.context():
        if feed_id:
            feed = FilterFeed.get_by_id(feed_id)
        else:
            feed = FilterFeed()
        if url:
            feed.url = url
        if query_builder:
            feed.query_builder = json.loads(query_builder)
        key = feed.put()
        return f"https://filter-feed.newg.as/v1/{key.id()}"

def main(_):
    print(upsert_feed(FLAGS.id, FLAGS.url, FLAGS.query_builder))

if __name__ == '__main__':
    app.run(main)

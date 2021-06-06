#!/usr/bin/env python3

import json

from google.cloud import ndb
from absl import app, flags

from filter_feed import FilterFeed

url = flags.DEFINE_string("url", None, "Upstream feed", required=True)
query_builder =  flags.DEFINE_string("query_builder", None, "querybuilder string to filter", required=True)

FLAGS = flags.FLAGS

def main(_):
    client = ndb.Client()
    with client.context():
        print( FLAGS.url)
        print( json.loads(FLAGS.query_builder))
        key = FilterFeed(
                url = FLAGS.url,
                query_builder = json.loads(FLAGS.query_builder),
                ).put()
        print(f"https://filter-feed.newg.as/{key.id()}")

if __name__ == '__main__':
    app.run(main)

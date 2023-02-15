
from absl import logging
import flask
from google.cloud import ndb  # type: Any
from opentelemetry import  trace
import json

import model

tracer = trace.get_tracer(__name__)

def list_feeds(request: flask.Request) -> flask.Response:
    client = ndb.Client()
    with client.context():
        filters = model.FilterFeed.query().iter()
        res = flask.render_template('list.html', filters=filters)
    return res

def get_feed(request: flask.Request,  feed_id: int) -> flask.Response:
    client = ndb.Client()
    with client.context():
        filter = model.FilterFeed.get_by_id(feed_id)
        if filter is None:
            flask.abort(404)
        res = flask.render_template('get.html', filter=filter,  new=False)
    return res

def create_feed_form(request: flask.Request) -> flask.Response:
    filter = model.FilterFeed()
    res = flask.render_template('get.html', filter=filter,  new=True)
    return res
    
def create_feed(request: flask.Request) -> flask.Response:
    client = ndb.Client()
    with client.context():
        feed = model.FilterFeed()
        feed.url = request.form["url"]
        feed.name = request.form["name"]
        feed.query_builder = json.loads(request.form["query_builder"])
        logging.info("Creating feed %s",  feed)
        key = feed.put()
        logging.info("Feed created with key %s",  key)
    return  flask.redirect(flask.url_for('list_feeds'))

def update_feed(request: flask.Request,  feed_id: int) -> flask.Response:
    client = ndb.Client()
    with client.context():
        feed = model.FilterFeed.get_by_id(feed_id)
        if feed is None:
            flask.abort(404)
        old_feed= repr(feed)
        feed.url = request.form["url"]
        feed.name = request.form["name"]
        feed.query_builder = json.loads(request.form["query_builder"])
        logging.info("Updating feed from %s to %s",  old_feed,  repr(feed))
        feed.put()
    return flask.redirect(flask.url_for('list_feeds'))

def delete_feed(request: flask.Request,  feed_id: int) -> flask.Response:
    client = ndb.Client()
    with client.context():
        feed = model.FilterFeed.get_by_id(feed_id)
        if feed is None:
            flask.abort(404)
        logging.info("Deleting feed %s",  feed)
        feed.key.delete()
    return flask.redirect(flask.url_for('list_feeds'))
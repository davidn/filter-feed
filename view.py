
from absl import logging
import flask
from flask_security.core import current_user
from typing import Any
from google.cloud import ndb  # type: Any
from opentelemetry import  trace
import json

import model
from flask_wtf.form import FlaskForm
from wtforms import StringField, URLField, HiddenField
from wtforms.validators import DataRequired, URL

tracer = trace.get_tracer(__name__)

class HiddenJsonField(HiddenField):
    def _value(self):
        return json.dumps(self.data)
    
    def process_formdata(self, valuelist):
        self.data = json.loads(valuelist[0])
    
class FeedForm(FlaskForm):
    name = StringField('Nickname', validators=[DataRequired()])
    url = URLField('URL', validators=[DataRequired(), URL()])
    query_builder = HiddenJsonField('Filter')

def list_feeds(request: flask.Request) -> flask.Response:
    if model.ListAllFiltersPermission.can():
        filters = model.FilterFeed.query().iter()
    else:
        filters = model.FilterFeed.query(ancestor=current_user.key).iter()
    return flask.render_template('list.html', filters=filters,
                                show_user_id=model.ListAllFiltersPermission.can())

def get_feed(request: flask.Request, key: ndb.Key) -> flask.Response:
    filter = key.get()
    if filter is None:
        flask.abort(404)
    form = FeedForm(obj=filter)
    return flask.render_template('get.html', form=form, filter=filter,  new=False)
    
def create_feed(request: flask.Request) -> flask.Response:
    feed = model.FilterFeed(parent=current_user.key)
    form = FeedForm()
    if form.validate_on_submit():
        feed.url = form.url.data
        feed.name = form.name.data
        feed.query_builder = form.query_builder.data
        logging.info("Creating feed %s",  feed)
        key = feed.put()
        logging.info("Feed created with key %s",  key)
        return flask.redirect(flask.url_for('list_feeds'))
    else:
        return flask.render_template('get.html', form=form, filter=filter,  new=True)
        

def update_feed(request: flask.Request,  key: ndb.Key) -> flask.Response:
    feed = key.get()
    if feed is None:
        flask.abort(404)
    old_feed = repr(feed)
    form = FeedForm()
    form.validate()
    feed.url = form.url.data
    feed.name = form.name.data
    feed.query_builder = form.query_builder.data
    logging.info("Updating feed from %s to %s",  old_feed,  repr(feed))
    feed.put()
    return flask.redirect(flask.url_for('list_feeds'))

def delete_feed(request: flask.Request, key: ndb.Key) -> flask.Response:
    feed = key.get()
    if feed is None:
        flask.abort(404)
    form = FeedForm()
    form.validate()  # still needex cor CSRF
    logging.info("Deleting feed %s",  feed)
    feed.key.delete()
    return flask.redirect(flask.url_for('list_feeds'))

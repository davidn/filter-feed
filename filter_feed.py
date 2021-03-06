from typing import Any
from google.cloud import ndb  # type: Any
from validators import url

from jqqb_evaluator.evaluator import Evaluator
from datetime import datetime

def validate_url(prop, value):
    assert url(value, public=True)
    return value

def validate_jqqb(prop, value):
    e = Evaluator(value)
    e.object_matches_rules({"title": "blah", "pubdate": datetime.min, "description": "desc"})
    return value

class FilterFeed(ndb.Model):
    url = ndb.StringProperty(required=True, validator=validate_url)
    query_builder = ndb.JsonProperty(required=True, validator=validate_jqqb)


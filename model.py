
from typing import Any
from google.cloud import ndb  # type: Any
from validators import url

from jqqb_evaluator.evaluator import Evaluator
from datetime import datetime

def validate_jqqb(value):
    try:
        _validate_jqqb(None,  value)
    except:
        return False
    return True

def _validate_url(prop, value):
    assert url(value, public=True)
    return value

def _validate_jqqb(prop, value):
    e = Evaluator(value)
    e.object_matches_rules({"title": "blah", "pubdate": datetime.min, "description": "desc"})
    return value

class FilterFeed(ndb.Model):
    url = ndb.StringProperty(required=True, validator=_validate_url)
    name = ndb.StringProperty(required=True)
    query_builder = ndb.JsonProperty(required=True, validator=_validate_jqqb)


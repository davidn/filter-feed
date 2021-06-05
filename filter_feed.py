
from google.cloud import ndb
from validators import url

from jqqb_evaluator.evaluator import Evaluator
from datetime import datetime

def validate_url(prop, value) -> bool:
    return url.url(value, public=True)

def validate_jqqb(prop, value) -> bool:
    e = Evaluator(value)
    e.object_matches_rules({"title": "blah", "pubdate": datetime.min, "description": "desc"})

class FilterFeed(ndb.Model):
    url = ndb.StringProperty(required=True, validator=validate_url)
    query_builder = ndb.JsonProperty(required=True, validator=validate_jqqb)

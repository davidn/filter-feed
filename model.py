
from typing import Any
from datetime import datetime
import dataclasses

from google.cloud import ndb  # type: Any
from validators import url
from jqqb_evaluator.evaluator import Evaluator

from item import Item

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
    
    # jqqb_evaluator assumes any non-AND condition is OR. However the JQQB UI rejects anything
    # other than capitalized AND and OR. This hack adds validation to ensure we aren't allowing
    # JQQB that the UI will choke on.
    def recurse_check_condition(d):
        assert(d["condition"] in ["AND", "OR"])
        for r in d["rules"]:
            if "rules" in r:
                recurse_check_condition(r)
    recurse_check_condition(value)
    
    # Also JQQB UI requires fixed id/fields but jqqb_evaluator is permissive. Lets validate this
    # ourselves.
    # JQQB that the UI will choke on.
    def recurse_check_fields(d):
        for r in d["rules"]:
            if "rules" in r:
                recurse_check_fields(r)
            else:
                assert(r["id"] in (f.name for f in dataclasses.fields(Item)))
    recurse_check_fields(value)
    
    return value


class FilterFeed(ndb.Model):
    url = ndb.StringProperty(required=True, validator=_validate_url)
    name = ndb.StringProperty(required=True)
    query_builder = ndb.JsonProperty(required=True, validator=_validate_jqqb)


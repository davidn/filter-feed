
from typing import Any
from datetime import datetime
import dataclasses
from functools import partial

from google.cloud import ndb  # type: Any
from validators import url
from jqqb_evaluator.evaluator import Evaluator
from flask_security import UserMixin, RoleMixin
from flask_principal import Permission, ItemNeed, RoleNeed

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


class Role(ndb.Model,  RoleMixin):
    name = ndb.StringProperty(required=True)
    description = ndb.StringProperty()
    
    @property
    def id(self):
        return self.key.id() if self.key else None


class User(ndb.Model,  UserMixin):
    email = ndb.StringProperty()
    password = ndb.StringProperty()
    active = ndb.BooleanProperty()
    confirmed_at = ndb.DateTimeProperty()
    role_keys = ndb.KeyProperty(kind=Role,  repeated=True)
    fs_uniquifier = ndb.StringProperty()
    
    def __init__(self, *args, **kwargs):
        self._roles = None
        super().__init__(*args, **kwargs)
    
    @property
    def id(self):
        return self.key.id() if self.key else None
    
    @property
    def roles(self):
        if self._roles is None:
            self._roles = [r for r in ndb.get_multi(self.role_keys) if r]
        return self._roles
        

FilterNeed = partial(ItemNeed, type='filter')
LoadFilterNeed = partial(FilterNeed, method='load')
ViewFilterNeed = partial(FilterNeed, method='view')
EditFilterNeed = partial(FilterNeed, method='edit')
DeleteFilterNeed = partial(FilterNeed, method='delete')
CreateFilterNeed = partial(FilterNeed, method='create')

FilterAdminRoleNeed = RoleNeed("filter_admin")

class FilterPermission(Permission):
    Need = None
    
    def __init__(self, filter_key: ndb.Key):
        need = self.Need(value=filter_key.urlsafe())
        self.filter_key = filter_key
        super().__init__(need)

    # Typical flask-principal usage has the _identity_ define what needs that
    # identity meets, and a permission just lists what needs are required.
    # I don't like this because it requires the identity to up-front
    # exhaustively list every granular thing the user has access to, which is
    # both inefficient and more importantly tightly couples identity and
    # functionality.
    # Instead I'm overriding how we determine if a permission should be granted.
    # I still implement needs so we don't depart too-far from flask-principal
    # norms, but it's not in practice how permissions is granted.
    def allows(self, identity):
        # If identity really wants to grant a need, lets still respect that.
        if super().allows(identity):
            return True
        
        # SU gets to access any feeds. Can't do this with a need as they are
        # usually "AND" together.
        if FilterAdminRoleNeed in identity.provides:
            return True
        
        if self.filter_key.root().kind() == "User" and str(self.filter_key.root().id()) == identity.id:
            return True
        return False


class LoadFilterPermission(FilterPermission):
    Need = LoadFilterNeed
    
    def allows(self, identity):
        return True


class ViewFilterPermission(FilterPermission):
    Need = ViewFilterNeed


class EditFilterPermission(FilterPermission):
    Need = EditFilterNeed


class DeleteFilterPermission(FilterPermission):
    Need = DeleteFilterNeed

ListAllFiltersPermission = Permission(FilterAdminRoleNeed)

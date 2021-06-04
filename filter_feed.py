
from google.cloud import ndb
from validators import url


class FilterFeed(ndb.Model):
    url = ndb.StringProperty(
            required=True,
            validator=lambda prop, value: url.url(value, public=True)
            )
    title_match = ndb.StringProperty(required=True)

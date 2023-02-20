
import dataclasses

from google.cloud import ndb
import flask_security

@dataclasses.dataclass
class FakeUser(flask_security.UserMixin):
    id: int = 949
    email: str = "a@example.com"
    fs_uniquifier: str = ""
    active: bool = True
    roles: list = dataclasses.field(default_factory=list)

    @property
    def key(self):
        return ndb.Key("User", self.id)

@dataclasses.dataclass
class FakeRole(flask_security.RoleMixin):
    id: int = 555
    name: str = "filter_admin"
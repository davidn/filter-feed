
from absl import logging

from google.cloud.ndb.query import FilterNode, OR
from google.cloud.ndb import Key
import flask_security.datastore
import  flask_security.utils

class NdbUserDatastore(flask_security.datastore.UserDatastore):
    """A NDB datastore implementation for Flask-Security.
    """
    # Datastore overrides
    def commit(self):
        pass

    def put(self, model):
        model.put()
        return model

    def delete(self, model):
        model.key.delete()
            
    # UserDatastore overrides
    def find_user(self, case_insensitive: bool = False, **kwargs):
        if case_insensitive:
            logging.warning("Case insensitive search requested but not possible.")
        query = self.user_model.query()
        for field,  value in kwargs.items():
            if field == "id":
                query = query.filter(self.user_model.key==Key(self.user_model, int(value)))
            else:
                query = query.filter(FilterNode(field,  "=",  value))
        res=query.get()
        logging.debug("find_user: %r->%r; with query %r",  kwargs,  res,  query)
        return res

    def find_role(self, role: str):
        return self.role_model.query().filter(self.role_model.name==role).get()

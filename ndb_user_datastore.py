
from absl import logging

from google.cloud.ndb.query import FilterNode, OR
from google.cloud.ndb import Key
import flask_security.datastore
import  flask_security.utils

class NdbUserDatastore(flask_security.datastore.UserDatastore):
    """A NDB datastore implementation for Flask-Security.
    """
    def commit(self):
        pass

    def put(self, model):
        model.put()
        return model

    def delete(self, model):
        model.key.delete()

    def get_user(self, id_or_email):
        try:
            res= self.user_model.get_by_id(int(id_or_email))
        except ValueError:
            or_nodes = []
            for attr in flask_security.utils.get_identity_attributes():
                or_nodes.append(FilterNode(attr,  "=",  id_or_email))
            res = self.user_model.query().filter(OR(*or_nodes)).get()
        logging.debug("get_user: %r->%r",  id_or_email,  res)
        return res
            

    def find_user(self, **kwargs):
        query = self.user_model.query()
        for field,  value in kwargs.items():
            if field == "id":
                query = query.filter(self.user_model.key==Key(self.user_model, int(value)))
            else:
                query = query.filter(FilterNode(field,  "=",  value))
        res=query.get()
        logging.debug("find_user: %r->%r; with query %r",  kwargs,  res,  query)
        return res

    def find_role(self, role):
        return self.role_model.query().filter(self.role_model.name==role).get()

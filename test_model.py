
import unittest

import flask_principal
from flask.globals import current_app
from google.cloud import ndb

import model
import ndb_mocks
from app import app

class TestValidateJQQB(unittest.TestCase):
    def test_valid_empty(self):
        jqqb = {"condition":"OR","rules":[]}
        self.assertTrue(model.validate_jqqb(jqqb))
        jqqb = {"condition":"AND","rules":[]}
        self.assertTrue(model.validate_jqqb(jqqb))

    def test_valid_title_match(self):
        jqqb = {"condition":"OR","rules":[{"field":"title","id":"title","input":"text","operator":"contains","type":"string","value":"CVO"}]}
        self.assertTrue(model.validate_jqqb(jqqb))

    def test_invalid_condition(self):
        jqqb = {"condition":"asdfasdf","rules":[]}
        self.assertFalse(model.validate_jqqb(jqqb))
        # no lower case allowed by UI elements
        jqqb = {"condition":"or","rules":[]}
        self.assertFalse(model.validate_jqqb(jqqb))
        jqqb = {"condition":"and","rules":[]}
        self.assertFalse(model.validate_jqqb(jqqb))

    def test_invalid_id(self):
        jqqb = {"condition":"OR","rules":[{"field":"title","id":"asdf","input":"text","operator":"contains","type":"string","value":"CVO"}]}
        self.assertFalse(model.validate_jqqb(jqqb))


class TestFilterPermission(unittest.TestCase):
    def setUp(self):
            # needed because flask-principal stores identity in app context
        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)
        
        # needed because Key relies on a context
        ctxmgr = ndb_mocks.MockNdbClient()().context()
        self.context = ctxmgr.__enter__()
        self.addCleanup(ctxmgr.__exit__, None, None, None)  # TODO: Use enterContext when 3.11 is standard
    
    def set_identity(self, identity):
        flask_principal.identity_changed.send(current_app._get_current_object(),
                              identity=identity)
    
    def test_wrong_user(self):
        self.set_identity(flask_principal.Identity(id="123"))
        key = ndb.Key("User", 666, "Filter", 321)
        
        permission = model.ViewFilterPermission(key)
        self.assertFalse(permission.can())
    
    def test_anonymous(self):
        self.set_identity(flask_principal.AnonymousIdentity())
        key = ndb.Key("User", 666, "Filter", 321)
        
        permission = model.ViewFilterPermission(key)
        self.assertFalse(permission.can())
    
    def test_legacy_key(self):
        self.set_identity(flask_principal.Identity(id="123"))
        key = ndb.Key("Filter", 321)
        
        permission = model.ViewFilterPermission(key)
        self.assertFalse(permission.can())
    
    def test_right_user(self):
        self.set_identity(flask_principal.Identity(id="123"))
        key = ndb.Key("User", 123, "Filter", 321)
        
        permission = model.ViewFilterPermission(key)
        self.assertTrue(permission.can())
    
    def test_admin_role(self):
        identity = flask_principal.Identity(id="123")
        identity.provides.add(model.FilterAdminRoleNeed)
        self.set_identity(identity)
        
        key = ndb.Key("Filter", 321)
        permission = model.ViewFilterPermission(key)
        self.assertTrue(permission.can())
        
        key = ndb.Key("User", 666, "Filter", 321)
        permission = model.ViewFilterPermission(key)
        self.assertTrue(permission.can())
    
    def test_need_granted(self):
        identity = flask_principal.Identity(id="123")
        key = ndb.Key("Filter", 321)
        identity.provides.add(model.ViewFilterNeed(value=key.urlsafe()))
        self.set_identity(identity)
        
        permission = model.ViewFilterPermission(key)
        self.assertTrue(permission.can())
        

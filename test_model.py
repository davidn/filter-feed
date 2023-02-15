
import unittest

import model
import ndb_mocks

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

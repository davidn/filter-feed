#!/usr/bin/env python3

import os
import unittest
from unittest import mock
from xml.etree import ElementTree as ET

import werkzeug
import requests_mock
from google.cloud.datastore_v1 import types as datastore_type
from google.cloud import ndb

import ndb_mocks
from app import app, cloud_ndb, valid_key_or_abort
from decorator import contextmanager

app.testing = True

TESTDATA = os.path.join(os.path.dirname(__file__),  'testdata/')
class TestApp(unittest.TestCase):

    def setUp(self):
        self.stub = ndb_mocks.MockDatastoreStub()
        self.ndb_patch = mock.patch.object(cloud_ndb.client, 'stub',
                new=self.stub)
        self.ndb_patch.start()
        self.addCleanup(self.ndb_patch.stop)

        self.requests = requests_mock.Mocker()
        self.requests.start()
        self.addCleanup(self.requests.stop)
        with open(os.path.join(TESTDATA,  "rss.xml")) as test_in:
            self.requests.get('http://example.com/a', text=test_in.read())
        
        self.client = app.test_client().__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)  # TODO: Use enterContext when 3.11 is standard

    def testAppLegacy(self):
        e = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://example.com/a"), 
            "name": datastore_type.Value(string_value="nickname"),  
            "query_builder": datastore_type.Value(blob_value=b'{"condition":"AND","rules":[{"id":"X","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')}, 
          key = {"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [{"kind": "FilterFeed", "id": 123}]})
        lookup_res = datastore_type.LookupResponse(found=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)

        r = self.client.get('/v1/123')

        self.assertEqual(
            ET.canonicalize(r.data),
            ET.canonicalize(from_file=os.path.join(TESTDATA,  "rss-filtered.xml")))

    def testApp(self):
        e = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://example.com/a"), 
            "name": datastore_type.Value(string_value="nickname"),  
            "query_builder": datastore_type.Value(blob_value=b'{"condition":"AND","rules":[{"id":"X","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')}, 
          key = {"partition_id":{"project_id":"blah"},"path": [
              {"kind": "User", "id": 949},{"kind": "FilterFeed", "id": 123}]})
        lookup_res = datastore_type.LookupResponse(found=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)

        r = self.client.get('/v1/agRibGFochsLEgRVc2VyGLUHDAsSCkZpbHRlckZlZWQYeww')
        
        self.assertEqual(
            ET.canonicalize(r.data),
            ET.canonicalize(from_file=os.path.join(TESTDATA,  "rss-filtered.xml")))
    
    
    def testUnkownLegacy404(self):
        e = datastore_type.Entity(key = {"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [{"kind": "FilterFeed", "id": 321}]})
        lookup_res = datastore_type.LookupResponse(missing=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)
        
        r = self.client.get('/v1/321')
        
        self.assertEqual(r.status_code,  404)
    
    
    def testUnkown404(self):
        e = datastore_type.Entity(key = {"partition_id":{"project_id":"blah"},"path": [
            {"kind": "User", "id": 949},{"kind": "FilterFeed", "id": 321}]})
        lookup_res = datastore_type.LookupResponse(missing=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)
        
        r = self.client.get('/v1/agRibGFochwLEgRVc2VyGLUHDAsSCkZpbHRlckZlZWQYwQIM')
        
        self.assertEqual(r.status_code,  404)


class TestKeyValidation(unittest.TestCase):
    def setUp(self):
        # needed because Key relies on a context
        ctxmgr = ndb_mocks.MockNdbClient()().context()
        self.context = ctxmgr.__enter__()
        self.addCleanup(ctxmgr.__exit__, None, None, None)  # TODO: Use enterContext when 3.11 is standard
        
    @contextmanager
    def assertNotRaises(self, exception, msg=None):
        try:
            yield
        except exception as e:
            self.fail(e)
            
    
    def test_non_filter(self):
        key = ndb.Key("foo", 123)
        with self.assertRaises(werkzeug.exceptions.NotFound):
            valid_key_or_abort(key)
        key = ndb.Key("User", 321, "bar", 123)
        with self.assertRaises(werkzeug.exceptions.NotFound):
            valid_key_or_abort(key)
    
    def test_too_long_path(self):
        key = ndb.Key("User", 321, "bar", 123, "FilterFeed", 654)
        with self.assertRaises(werkzeug.exceptions.NotFound):
            valid_key_or_abort(key)
    
    def test_root_non_user(self):
        key = ndb.Key("bar", 123, "FilterFeed", 654)
        with self.assertRaises(werkzeug.exceptions.NotFound):
            valid_key_or_abort(key)
    
    def test_valid(self):
        key = ndb.Key("FilterFeed", 654)
        with self.assertNotRaises(werkzeug.exceptions.NotFound):
            valid_key_or_abort(key)
        key = ndb.Key("User", 123, "FilterFeed", 654)        
        with self.assertNotRaises(werkzeug.exceptions.NotFound):
            valid_key_or_abort(key)
    
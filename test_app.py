#!/usr/bin/env python3

import os
import unittest
from unittest import mock
from xml.etree import ElementTree as ET

import werkzeug
from werkzeug.routing import ValidationError, Map
import requests_mock
from google.cloud.datastore_v1 import types as datastore_type
from google.cloud import ndb

import ndb_mocks
from app import app, cloud_ndb, KeyConverter

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
          key = {"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [
              {"kind": "User", "id": 949},{"kind": "FilterFeed", "id": 123}]})
        lookup_res = datastore_type.LookupResponse(found=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)

        r = self.client.get('/v1/949/123')
        self.assertEqual(
            ET.canonicalize(r.data),
            ET.canonicalize(from_file=os.path.join(TESTDATA,  "rss-filtered.xml")))
    
    
    def testUnkownLegacy404(self):
        e = datastore_type.Entity(key = {
            "partition_id":{"project_id":app.config["NDB_PROJECT"]},
            "path": [{"kind": "FilterFeed", "id": 321}]})
        lookup_res = datastore_type.LookupResponse(missing=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)
        
        r = self.client.get('/v1/321')
        
        self.assertEqual(r.status_code,  404)
    
    
    def testUnkownUser404(self):
        e = datastore_type.Entity(key = {
            "partition_id":{"project_id":app.config["NDB_PROJECT"]},
            "path": [{"kind": "User", "id": 666},{"kind": "FilterFeed", "id": 321}]})
        lookup_res = datastore_type.LookupResponse(missing=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)
        
        r = self.client.get('/v1/666/321')
        
        self.assertEqual(r.status_code,  404)
    
    
    def testUnkownFeed404(self):
        e = datastore_type.Entity(key = {
            "partition_id":{"project_id":app.config["NDB_PROJECT"]},
            "path": [{"kind": "User", "id": 949},{"kind": "FilterFeed", "id": 123}]})
        lookup_res = datastore_type.LookupResponse(missing=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)
        
        r = self.client.get('/v1/949/123')
        
        self.assertEqual(r.status_code,  404)
        
class KeyConverterTest(unittest.TestCase):
    def setUp(self):
        self.map = Map()
        # needed because Key relies on a context
        ctxmgr = ndb_mocks.MockNdbClient()().context()
        self.context = ctxmgr.__enter__()
        self.addCleanup(ctxmgr.__exit__, None, None, None)  # TODO: Use enterContext when 3.11 is standard

    def test_legacy_id(self):
        self.assertEqual(
            KeyConverter(self.map).to_python("123"),
            ("FilterFeed", 123))
        self.assertEqual(
            KeyConverter(self.map).to_url(("FilterFeed", 123)),
            "123")
        self.assertEqual(
            KeyConverter(self.map).to_url(ndb.Key("FilterFeed", 123)),
            "123")

    def test_pair_id(self):
        self.assertEqual(
            KeyConverter(self.map).to_python("949/123"),
            ("User", 949, "FilterFeed", 123))
        self.assertEqual(
            KeyConverter(self.map).to_url(("User", 949, "FilterFeed", 123)),
            "949/123")
        self.assertEqual(
            KeyConverter(self.map).to_url(ndb.Key("User", 949, "FilterFeed", 123)),
            "949/123")

    def test_reject_triple(self):
        with self.assertRaises(ValidationError):
            KeyConverter(self.map).to_python("949/123/653")

    def test_reject_empty(self):
        with self.assertRaises(ValidationError):
            KeyConverter(self.map).to_python("")
        with self.assertRaises(ValidationError):
            KeyConverter(self.map).to_python("1/")
        with self.assertRaises(ValidationError):
            KeyConverter(self.map).to_python("/1")

    def test_reject_nondigit(self):
        with self.assertRaises(ValidationError):
            KeyConverter(self.map).to_python("ab12")
        with self.assertRaises(ValidationError):
            KeyConverter(self.map).to_python("12/a3")
        with self.assertRaises(ValidationError):
            KeyConverter(self.map).to_python("12w/3")
        with self.assertRaises(ValidationError):
            KeyConverter(self.map).to_python("12_")
    
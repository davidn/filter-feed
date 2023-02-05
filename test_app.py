#!/usr/bin/env python3

import os
import unittest
from unittest import mock
from xml.etree import ElementTree as ET

import requests_mock
from google.cloud.datastore_v1 import types as datastore_type

import ndb_mocks
from app import app

app.testing = True

TESTDATA = os.path.join(os.path.dirname(__file__),  'testdata/')
class TestApp(unittest.TestCase):
    def run(self, result=None):
        with app.test_client() as client:
            self.client = client
            super().run(result)

    def setUp(self):
        self.ndb = ndb_mocks.MockNdbClient()
        self.ndb_patch = mock.patch(
                'google.cloud.ndb.Client',
                new=self.ndb)
        self.ndb_patch.start()
        self.addCleanup(self.ndb_patch.stop)

        self.requests = requests_mock.Mocker()
        self.requests.start()
        self.addCleanup(self.requests.stop)
        with open(os.path.join(TESTDATA,  "rss.xml")) as test_in:
            self.requests.get('http://example.com/a', text=test_in.read())

    def testApp(self):
        e = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://example.com/a"), 
            "name": datastore_type.Value(string_value="nickname"),  
            "query_builder": datastore_type.Value(blob_value=b'{"condition":"AND","rules":[{"id":"X","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')}, 
          key = {"partition_id":{"project_id":"blah"},"path": [{"kind": "FilterFeed", "id": 123}]})
        lookup_res = datastore_type.LookupResponse(found=[{"entity":e}])
        self.ndb.stub.lookup.set_val(lookup_res)
        r = self.client.get('/v1/123')
        self.assertEqual(
            ET.canonicalize(r.data),
            ET.canonicalize(from_file=os.path.join(TESTDATA,  "rss-filtered.xml")))
    
    def testStrIdIs404(self):
        r = self.client.get('/v1/abc')
        self.assertEqual(r.status_code,  404)
    
    def testUnkown404(self):
        e = datastore_type.Entity(key = {"partition_id":{"project_id":"blah"},"path": [{"kind": "FilterFeed", "id": 321}]})
        lookup_res = datastore_type.LookupResponse(missing=[{"entity":e}])
        self.ndb.stub.lookup.set_val(lookup_res)
        r = self.client.get('/v1/321')
        self.assertEqual(r.status_code,  404)

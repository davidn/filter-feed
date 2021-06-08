#!/usr/bin/env python3

import unittest
from unittest import mock
from xml.etree import ElementTree as ET

import requests_mock
from google.cloud.datastore_v1.proto import datastore_pb2

import ndb_mocks
from app import app

app.testing = True

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
        with open("testdata/rss.xml") as test_in:
            self.requests.get('http://example.com/a', text=test_in.read())

    def testApp(self):
        lookup_res = datastore_pb2.LookupResponse()
        e = lookup_res.found.add().entity
        e.properties["url"].string_value = "http://example.com/a"
        e.properties["query_builder"].blob_value = b'{"condition":"AND","rules":[{"id":"X","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}'
        path = e.key.partition_id.project_id='blah'
        path = e.key.path.add()
        path.kind="FilterFeed"
        path.id=123
        self.ndb.stub.Lookup.set_val(lookup_res)
        r = self.client.get('/v1/123')
        with open("testdata/rss-filtered.xml") as test_out:
            self.assertEquals(r.data, ET.tostring(ET.fromstring((test_out.read()))))

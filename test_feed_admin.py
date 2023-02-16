#!/usr/bin/env python3

from unittest import mock
import unittest

from google.cloud.datastore_v1 import types as datastore_type

import faulthandler
faulthandler.enable()

import feed_admin
import ndb_mocks

URL = "http://www.example.com/b"
NAME = "some nickname"
QB = '{"condition":"OR","rules":[{"type":"string","input":"text","id":"title","field":"title","operator":"not_contains","value":"CVO"}]}'


class TestUpsertFeed(unittest.TestCase):
    def setUp(self):
        self.client = ndb_mocks.MockNdbClient()
        self.client_patch = mock.patch(
                'google.cloud.ndb.Client',
                new=self.client)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    def testNewFeed(self):
        mr = datastore_type.MutationResult(key = {"partition_id":{"project_id":"blah"},"path": [{"kind": "FilterFeed", "id": 123}]})
        commit_res = datastore_type.CommitResponse(mutation_results=[mr])
        self.client.stub.commit.set_val(commit_res)
        self.assertEqual(
            feed_admin.upsert_feed(None, URL, NAME, QB),
            "https://filter-feed.newg.as/v1/123")
        self.client.stub.commit.assert_called_once()
        commit_req = self.client.stub.commit.call_args[0][0]
        self.assertEqual(len(commit_req.mutations), 1)
        self.assertTrue(commit_req.mutations[0].upsert is not None)
        self.assertEqual(commit_req.mutations[0].upsert.properties["url"].string_value, URL)
        self.assertEqual(commit_req.mutations[0].upsert.properties["name"].string_value, NAME)
        self.assertEqual(commit_req.mutations[0].upsert.properties["query_builder"].blob_value, bytes(QB, encoding='utf-8'))

    def testUpdateFeedURL(self):
        e = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://old_url/"), 
            "query_builder": datastore_type.Value(blob_value=bytes(QB, encoding='utf-8')), 
            "name": datastore_type.Value(string_value=NAME)}, 
          key = {"partition_id":{"project_id":"blah"},"path": [{"kind": "FilterFeed", "id": 123}]})
        lookup_res = datastore_type.LookupResponse(found=[{"entity":e}])
        self.client.stub.lookup.set_val(lookup_res)
        mr = datastore_type.MutationResult(key = {"partition_id":{"project_id":"blah"},"path": [{"kind": "FilterFeed", "id": 123}]})
        commit_res = datastore_type.CommitResponse(mutation_results=[mr])
        self.client.stub.commit.set_val(commit_res)
        self.assertEqual(
            feed_admin.upsert_feed(123, URL, None, None),
            "https://filter-feed.newg.as/v1/123")
        self.client.stub.lookup.assert_called_once()
        lookup_req = self.client.stub.lookup.call_args[0][0]
        self.assertEqual(len(lookup_req.keys), 1)
        self.assertEqual(len(lookup_req.keys[0].path), 1)
        self.assertEqual(lookup_req.keys[0].path[0].id, 123)
        self.client.stub.commit.assert_called_once()
        commit_req = self.client.stub.commit.call_args[0][0]
        self.assertEqual(len(commit_req.mutations), 1)
        self.assertTrue(commit_req.mutations[0].upsert is not None)
        self.assertEqual(len(commit_req.mutations[0].upsert.key.path), 1)
        self.assertEqual(commit_req.mutations[0].upsert.key.path[0].id, 123)
        self.assertEqual(commit_req.mutations[0].upsert.properties["url"].string_value, URL)
        self.assertEqual(commit_req.mutations[0].upsert.properties["query_builder"].blob_value, bytes(QB, encoding='utf-8'))

    def testUpdateFeedName(self):
        e = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value=URL), 
            "query_builder": datastore_type.Value(blob_value=bytes(QB, encoding='utf-8'))}, 
          key = {"partition_id":{"project_id":"blah"},"path": [{"kind": "FilterFeed", "id": 123}]})
        lookup_res = datastore_type.LookupResponse(found=[{"entity":e}])
        self.client.stub.lookup.set_val(lookup_res)
        mr = datastore_type.MutationResult(key = {"partition_id":{"project_id":"blah"},"path": [{"kind": "FilterFeed", "id": 123}]})
        commit_res = datastore_type.CommitResponse(mutation_results=[mr])
        self.client.stub.commit.set_val(commit_res)
        self.assertEqual(
            feed_admin.upsert_feed(123, None, NAME, None),
            "https://filter-feed.newg.as/v1/123")
        self.client.stub.lookup.assert_called_once()
        lookup_req = self.client.stub.lookup.call_args[0][0]
        self.assertEqual(len(lookup_req.keys), 1)
        self.assertEqual(len(lookup_req.keys[0].path), 1)
        self.assertEqual(lookup_req.keys[0].path[0].id, 123)
        self.client.stub.commit.assert_called_once()
        commit_req = self.client.stub.commit.call_args[0][0]
        self.assertEqual(len(commit_req.mutations), 1)
        self.assertTrue(commit_req.mutations[0].upsert is not None)
        self.assertEqual(len(commit_req.mutations[0].upsert.key.path), 1)
        self.assertEqual(commit_req.mutations[0].upsert.key.path[0].id, 123)
        self.assertEqual(commit_req.mutations[0].upsert.properties["url"].string_value, URL)
        self.assertEqual(commit_req.mutations[0].upsert.properties["name"].string_value, NAME)
        self.assertEqual(commit_req.mutations[0].upsert.properties["query_builder"].blob_value, bytes(QB, encoding='utf-8'))



if __name__ == "__main__":
    unittest.main()

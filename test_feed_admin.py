#!/usr/bin/env python3

from unittest import mock
import unittest

from google.cloud import ndb
from google.cloud.datastore_v1.proto import datastore_pb2

import faulthandler
faulthandler.enable()

import feed_admin
import ndb_mocks

URL = "http://www.example.com/b"
NAME = "some nickname"
QB = '{"condition":"or","rules":[{"type":"string","input":"text","id":"selects","field":"title","operator":"not_contains","value":"CVO"}]}'


class TestUpsertFeed(unittest.TestCase):
    def setUp(self):
        self.client = ndb_mocks.MockNdbClient()
        self.client_patch = mock.patch(
                'google.cloud.ndb.Client',
                new=self.client)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    def testNewFeed(self):
        commit_res = datastore_pb2.CommitResponse()
        mr = commit_res.mutation_results.add()
        path = mr.key.partition_id.project_id='blah'
        path = mr.key.path.add()
        path.kind="FilterFeed"
        path.id=123
        self.client.stub.Commit.set_val(commit_res)
        self.assertEqual(
            feed_admin.upsert_feed(None, URL, NAME, QB),
            "https://filter-feed.newg.as/v1/123")
        self.client.stub.Commit.assert_called_once()
        commit_req = self.client.stub.Commit.call_args[0][0]
        self.assertEqual(len(commit_req.mutations), 1)
        self.assertTrue(commit_req.mutations[0].HasField("upsert"))
        self.assertEqual(commit_req.mutations[0].upsert.properties["url"].string_value, URL)
        self.assertEqual(commit_req.mutations[0].upsert.properties["name"].string_value, NAME)
        self.assertEqual(commit_req.mutations[0].upsert.properties["query_builder"].blob_value, bytes(QB, encoding='utf-8'))

    def testNewFeedNoName(self):
        commit_res = datastore_pb2.CommitResponse()
        mr = commit_res.mutation_results.add()
        path = mr.key.partition_id.project_id='blah'
        path = mr.key.path.add()
        path.kind="FilterFeed"
        path.id=123
        self.client.stub.Commit.set_val(commit_res)
        self.assertEqual(
            feed_admin.upsert_feed(None, URL, None, QB),
            "https://filter-feed.newg.as/v1/123")
        self.client.stub.Commit.assert_called_once()
        commit_req = self.client.stub.Commit.call_args[0][0]
        self.assertEqual(len(commit_req.mutations), 1)
        self.assertTrue(commit_req.mutations[0].HasField("upsert"))
        self.assertEqual(commit_req.mutations[0].upsert.properties["url"].string_value, URL)
        self.assertEqual(commit_req.mutations[0].upsert.properties["query_builder"].blob_value, bytes(QB, encoding='utf-8'))

    def testUpdateFeedURL(self):
        lookup_res = datastore_pb2.LookupResponse()
        e = lookup_res.found.add().entity
        e.properties["url"].string_value = "http://old_url/"
        e.properties["query_builder"].blob_value = bytes(QB, encoding='utf-8')
        path = e.key.partition_id.project_id='blah'
        path = e.key.path.add()
        path.kind="FilterFeed"
        path.id=123
        self.client.stub.Lookup.set_val(lookup_res)
        commit_res = datastore_pb2.CommitResponse()
        mr = commit_res.mutation_results.add()
        path = mr.key.partition_id.project_id='blah'
        path = mr.key.path.add()
        path.kind="FilterFeed"
        path.id=123
        self.client.stub.Commit.set_val(commit_res)
        self.assertEqual(
            feed_admin.upsert_feed(123, URL, None, None),
            "https://filter-feed.newg.as/v1/123")
        self.client.stub.Lookup.assert_called_once()
        lookup_req = self.client.stub.Lookup.call_args[0][0]
        self.assertEqual(len(lookup_req.keys), 1)
        self.assertEqual(len(lookup_req.keys[0].path), 1)
        self.assertEqual(lookup_req.keys[0].path[0].id, 123)
        self.client.stub.Commit.assert_called_once()
        commit_req = self.client.stub.Commit.call_args[0][0]
        self.assertEqual(len(commit_req.mutations), 1)
        self.assertTrue(commit_req.mutations[0].HasField("upsert"))
        self.assertEqual(len(commit_req.mutations[0].upsert.key.path), 1)
        self.assertEqual(commit_req.mutations[0].upsert.key.path[0].id, 123)
        self.assertEqual(commit_req.mutations[0].upsert.properties["url"].string_value, URL)
        self.assertEqual(commit_req.mutations[0].upsert.properties["query_builder"].blob_value, bytes(QB, encoding='utf-8'))

    def testUpdateFeedName(self):
        lookup_res = datastore_pb2.LookupResponse()
        e = lookup_res.found.add().entity
        e.properties["url"].string_value = URL
        e.properties["name"].string_value = "old_name"
        e.properties["query_builder"].blob_value = bytes(QB, encoding='utf-8')
        path = e.key.partition_id.project_id='blah'
        path = e.key.path.add()
        path.kind="FilterFeed"
        path.id=123
        self.client.stub.Lookup.set_val(lookup_res)
        commit_res = datastore_pb2.CommitResponse()
        mr = commit_res.mutation_results.add()
        path = mr.key.partition_id.project_id='blah'
        path = mr.key.path.add()
        path.kind="FilterFeed"
        path.id=123
        self.client.stub.Commit.set_val(commit_res)
        self.assertEqual(
            feed_admin.upsert_feed(123, None, NAME, None),
            "https://filter-feed.newg.as/v1/123")
        self.client.stub.Lookup.assert_called_once()
        lookup_req = self.client.stub.Lookup.call_args[0][0]
        self.assertEqual(len(lookup_req.keys), 1)
        self.assertEqual(len(lookup_req.keys[0].path), 1)
        self.assertEqual(lookup_req.keys[0].path[0].id, 123)
        self.client.stub.Commit.assert_called_once()
        commit_req = self.client.stub.Commit.call_args[0][0]
        self.assertEqual(len(commit_req.mutations), 1)
        self.assertTrue(commit_req.mutations[0].HasField("upsert"))
        self.assertEqual(len(commit_req.mutations[0].upsert.key.path), 1)
        self.assertEqual(commit_req.mutations[0].upsert.key.path[0].id, 123)
        self.assertEqual(commit_req.mutations[0].upsert.properties["url"].string_value, URL)
        self.assertEqual(commit_req.mutations[0].upsert.properties["name"].string_value, NAME)
        self.assertEqual(commit_req.mutations[0].upsert.properties["query_builder"].blob_value, bytes(QB, encoding='utf-8'))



if __name__ == "__main__":
    unittest.main()

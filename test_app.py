#!/usr/bin/env python3

import os
from unittest import mock
import unittest
from xml.etree import ElementTree as ET

from flask_login.test_client import FlaskLoginClient
from google.cloud import ndb
from google.cloud.datastore_v1 import types as datastore_type
import requests_mock
import werkzeug
from werkzeug.routing import ValidationError, Map

from app import app, cloud_ndb, KeyConverter
import model
import ndb_mocks
import ndb_user_datastore
import dataclasses
from fake_user import FakeUser, FakeRole

app.testing = True

TESTDATA = os.path.join(os.path.dirname(__file__),  'testdata/')


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.stub = ndb_mocks.MockDatastoreStub()
        self.ndb_patch = mock.patch.object(cloud_ndb.client, 'stub',
                new=self.stub)
        self.ndb_patch.start()
        self.addCleanup(self.ndb_patch.stop)
        
        if hasattr(self, "user"):
            self.find_user_patch = mock.patch.object(
                ndb_user_datastore.NdbUserDatastore, 'find_user')
            self.find_user_patch.start()
            self.addCleanup(self.find_user_patch.stop)
            ndb_user_datastore.NdbUserDatastore.find_user.return_value = self.user
        
        self.find_role_patch = mock.patch.object(
            ndb_user_datastore.NdbUserDatastore, 'find_role')
        self.find_role_patch.start()
        self.addCleanup(self.find_role_patch.stop)
        ndb_user_datastore.NdbUserDatastore.find_role.return_value = FakeRole()
        
        app.config["WTF_CSRF_ENABLED"] = False
        app.test_client_class = FlaskLoginClient
        self.client = app.test_client(user=getattr(self, 'user', None)).__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)  # TODO: Use enterContext when 3.11 is standard

class TestApply(AppTestCase):
    def setUp(self):
        super().setUp()
        self.requests = requests_mock.Mocker()
        self.requests.start()
        self.addCleanup(self.requests.stop)
        with open(os.path.join(TESTDATA,  "rss.xml")) as test_in:
            self.requests.get('http://example.com/a', text=test_in.read())

    def test_legacy(self):
        e = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://example.com/a"), 
            "name": datastore_type.Value(string_value="nickname"),  
            "query_builder": datastore_type.Value(blob_value=b'{"condition":"AND","rules":[{"id":"X","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')}, 
          key = {"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [{"kind": "FilterFeed", "id": 123}]})
        lookup_res = datastore_type.LookupResponse(found=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)

        r = self.client.get('/v1/123')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            ET.canonicalize(r.data),
            ET.canonicalize(from_file=os.path.join(TESTDATA,  "rss-filtered.xml")))

    def test_success(self):
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

        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            ET.canonicalize(r.data),
            ET.canonicalize(from_file=os.path.join(TESTDATA,  "rss-filtered.xml")))
    
    
    def test_legacy_unknown(self):
        e = datastore_type.Entity(key = {
            "partition_id":{"project_id":app.config["NDB_PROJECT"]},
            "path": [{"kind": "FilterFeed", "id": 321}]})
        lookup_res = datastore_type.LookupResponse(missing=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)
        
        r = self.client.get('/v1/321')
        
        self.assertEqual(r.status_code,  404)
    
    
    def test_unknown_user(self):
        e = datastore_type.Entity(key = {
            "partition_id":{"project_id":app.config["NDB_PROJECT"]},
            "path": [{"kind": "User", "id": 666},{"kind": "FilterFeed", "id": 321}]})
        lookup_res = datastore_type.LookupResponse(missing=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)
        
        r = self.client.get('/v1/666/321')
        
        self.assertEqual(r.status_code,  404)
    
    
    def test_unknown_feed(self):
        e = datastore_type.Entity(key = {
            "partition_id":{"project_id":app.config["NDB_PROJECT"]},
            "path": [{"kind": "User", "id": 949},{"kind": "FilterFeed", "id": 123}]})
        lookup_res = datastore_type.LookupResponse(missing=[{"entity":e}])
        self.stub.lookup.set_val(lookup_res)
        
        r = self.client.get('/v1/949/123')
        
        self.assertEqual(r.status_code,  404)

class TestLoginRequired(AppTestCase):
    def test_list(self):
        r = self.client.get('/')
        self.assertNotEqual(r.status_code, 200)
        self.stub.lookup.assert_not_called()
        self.stub.commit.assert_not_called()
    def test_create(self):
        r = self.client.get('/v1/create')
        self.assertNotEqual(r.status_code, 200)
        self.stub.lookup.assert_not_called()
        self.stub.commit.assert_not_called()
    def test_update(self):
        r = self.client.post('/v1/123/edit')
        self.assertNotEqual(r.status_code, 200)
        self.stub.lookup.assert_not_called()
        self.stub.commit.assert_not_called()
    def test_get(self):
        r = self.client.get('/v1/123/edit')
        self.assertNotEqual(r.status_code, 200)
        self.stub.lookup.assert_not_called()
        self.stub.commit.assert_not_called()
    def test_delete(self):
        r = self.client.post('/v1/123/456/delete')
        self.assertNotEqual(r.status_code, 200)
        self.stub.lookup.assert_not_called()
        self.stub.commit.assert_not_called()
    

class TestList(AppTestCase):
    def setUp(self):
        self.user = FakeUser()
        super().setUp()
    
    def test_success(self):
        e1 = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://example.com/a"), 
            "name": datastore_type.Value(string_value="nicknameA"),  
            "query_builder": datastore_type.Value(blob_value=b'{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')},
          key = {"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [
              {"kind": "User", "id": 949},{"kind": "FilterFeed", "id": 123}]}) 
        e2 = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://example.com/b"), 
            "name": datastore_type.Value(string_value="nicknameB"),  
            "query_builder": datastore_type.Value(blob_value=b'{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')},
          key = {"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [
              {"kind": "User", "id": 949},{"kind": "FilterFeed", "id": 456}]}) 
        b = datastore_type.QueryResultBatch(
            entity_results=[{"entity":e1},{"entity":e2}],
            more_results="NO_MORE_RESULTS",
            entity_result_type="FULL")
        self.stub.run_query.set_val(datastore_type.RunQueryResponse(batch=b))

        r = self.client.get('/')
        
        self.assertEqual(r.status_code, 200)
        # check some stuff from e1 and e2 are in the response.
        self.assertIn("http://example.com/a", r.text)
        self.assertIn("nicknameA", r.text)
        self.assertIn("/v1/949/123/edit", r.text)
        self.assertIn("http://example.com/b", r.text)
        self.assertIn("nicknameB", r.text)
        self.assertIn("/v1/949/456/edit", r.text)
        # Check the call
        self.stub.run_query.assert_called_once()
        self.assertEqual(
            self.stub.run_query.call_args.args[0].query.kind,
            [datastore_type.KindExpression(name="FilterFeed")])
        self.assertEqual(
            self.stub.run_query.call_args.args[0].query.filter.property_filter,
            datastore_type.PropertyFilter(property={"name": "__key__"},
                                          op="HAS_ANCESTOR",
                                          value={"key_value":{"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [
              {"kind": "User", "id": 949}]}}))
    
    def test_admin_list(self):
        # THis test just makes sure we call without an ancestor filter
        self.user.roles = [FakeRole()]
        
        b = datastore_type.QueryResultBatch(
            entity_results=[],
            more_results="NO_MORE_RESULTS",
            entity_result_type="FULL")
        self.stub.run_query.set_val(datastore_type.RunQueryResponse(batch=b))

        r = self.client.get('/')
        
        self.assertEqual(r.status_code, 200)
        # Check the call
        self.stub.run_query.assert_called_once()
        self.assertEqual(
            self.stub.run_query.call_args.args[0].query.kind,
            [datastore_type.KindExpression(name="FilterFeed")])
        self.assertFalse(
            self.stub.run_query.call_args.args[0].query.filter.property_filter)    


class TestGet(AppTestCase):
    def setUp(self):
        self.user = FakeUser()
        super().setUp()
    
    def test_wrong_user(self):
        r = self.client.get('/v1/666/123/edit')
        self.assertEqual(r.status_code, 403)
        self.stub.lookup.assert_not_called()
    
    def test_legacy(self):
        r = self.client.get('/v1/123/edit')
        self.assertEqual(r.status_code, 403)
        self.stub.lookup.assert_not_called()
    
    def test_success(self):
        e = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://example.com/a"), 
            "name": datastore_type.Value(string_value="nicknameA"),  
            "query_builder": datastore_type.Value(blob_value=b'{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')},
          key = {"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [
              {"kind": "User", "id": 949},{"kind": "FilterFeed", "id": 123}]}) 
        self.stub.lookup.set_val(datastore_type.LookupResponse(found=[{"entity":e}]))

        r = self.client.get('/v1/949/123/edit')
        
        self.assertEqual(r.status_code, 200)
        self.assertIn("http://example.com/a", r.text)
        self.assertIn("nicknameA", r.text)
        self.assertIn("Boring", r.text)
        self.assertIn("/v1/949/123/delete", r.text)

    
    def test_legacy_admin(self):
        # THis test just makes sure we call without an ancestor filter
        self.user.roles = [FakeRole()]
        e = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://example.com/a"), 
            "name": datastore_type.Value(string_value="nicknameA"),  
            "query_builder": datastore_type.Value(blob_value=b'{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')},
          key = {"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [
              {"kind": "FilterFeed", "id": 123}]}) 
        self.stub.lookup.set_val(datastore_type.LookupResponse(found=[{"entity":e}]))

        r = self.client.get('/v1/123/edit')
        
        self.assertEqual(r.status_code, 200)

    def test_admin(self):
        # THis test just makes sure we call without an ancestor filter
        self.user.roles = [FakeRole()]
        e = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://example.com/a"), 
            "name": datastore_type.Value(string_value="nicknameA"),  
            "query_builder": datastore_type.Value(blob_value=b'{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')},
          key = {"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [
              {"kind": "User", "id": 666},{"kind": "FilterFeed", "id": 123}]}) 
        self.stub.lookup.set_val(datastore_type.LookupResponse(found=[{"entity":e}]))

        r = self.client.get('/v1/666/123/edit')
        
        self.assertEqual(r.status_code, 200)
    

class TestCreate(AppTestCase):
    def setUp(self):
        self.user = FakeUser()
        super().setUp()
    
    def test_success(self):
        mr = datastore_type.MutationResult(key = {
            "partition_id":{"project_id":"blah"},
            "path": [{"kind": "User", "id": 949}, {"kind": "FilterFeed", "id": 123}]})
        self.stub.commit.set_val(datastore_type.CommitResponse(mutation_results=[mr]))

        r = self.client.post('/v1/create', data={
            "url": "http://example.com/a",
            "name": "Nickname",
            "query_builder": '{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}'
            })
        
        self.assertEqual(r.status_code, 302)
        # Check the call
        self.stub.commit.assert_called_once()
        commit_req = self.stub.commit.call_args[0][0]
        self.assertEqual(len(commit_req.mutations), 1)
        self.assertTrue(commit_req.mutations[0].upsert is not None)
        self.assertEqual(commit_req.mutations[0].upsert.properties["url"].string_value, "http://example.com/a")
        self.assertEqual(commit_req.mutations[0].upsert.properties["name"].string_value, "Nickname")
        self.assertEqual(commit_req.mutations[0].upsert.properties["query_builder"].blob_value, b'{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')
    

class TestUpdate(AppTestCase):
    def setUp(self):
        self.user = FakeUser()
        super().setUp()
    
    def test_wrong_user(self):
        r = self.client.post('/v1/666/123/edit', data={
            "url": "http://example.com/B",
            "name": "NicknameB",
            "query_builder": '{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Interesting"}]}'
            })
        self.assertEqual(r.status_code, 403)
        self.stub.commit.assert_not_called()
    
    def test_legacy(self):
        r = self.client.post('/v1/123/edit', data={
            "url": "http://example.com/B",
            "name": "NicknameB",
            "query_builder": '{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Interesting"}]}'
            })
        self.assertEqual(r.status_code, 403)
        self.stub.commit.assert_not_called()
    
    def test_success(self):
        e = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://example.com/a"), 
            "name": datastore_type.Value(string_value="nicknameA"),  
            "query_builder": datastore_type.Value(blob_value=b'{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')},
          key = {"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [
              {"kind": "User", "id": 949}, {"kind": "FilterFeed", "id": 123}]}) 
        self.stub.lookup.set_val(datastore_type.LookupResponse(found=[{"entity":e}]))
        mr = datastore_type.MutationResult(key = {
            "partition_id":{"project_id":"blah"},
            "path": [{"kind": "User", "id": 949}, {"kind": "FilterFeed", "id": 123}]})
        self.stub.commit.set_val(datastore_type.CommitResponse(mutation_results=[mr]))

        r = self.client.post('/v1/949/123/edit', data={
            "url": "http://example.com/B",
            "name": "NicknameB",
            "query_builder": '{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Interesting"}]}'
            })
        
        self.assertEqual(r.status_code, 302)
        # Check the call
        self.stub.commit.assert_called_once()
        commit_req = self.stub.commit.call_args[0][0]
        self.assertEqual(len(commit_req.mutations), 1)
        self.assertTrue(commit_req.mutations[0].upsert is not None)
        self.assertEqual(commit_req.mutations[0].upsert.key, e.key)
        self.assertEqual(commit_req.mutations[0].upsert.properties["url"].string_value, "http://example.com/B")
        self.assertEqual(commit_req.mutations[0].upsert.properties["name"].string_value, "NicknameB")
        self.assertEqual(commit_req.mutations[0].upsert.properties["query_builder"].blob_value, b'{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Interesting"}]}')

   
class TestDelete(AppTestCase):
    def setUp(self):
        self.user = FakeUser()
        super().setUp()
    
    def test_wrong_user(self):
        r = self.client.post('/v1/666/123/delete')
        self.assertEqual(r.status_code, 403)
        self.stub.commit.assert_not_called()
    
    def test_legacy(self):
        r = self.client.post('/v1/123/delete')
        self.assertEqual(r.status_code, 403)
        self.stub.commit.assert_not_called()
    
    def test_success(self):
        e = datastore_type.Entity(
          properties = {
            "url": datastore_type.Value(string_value="http://example.com/a"), 
            "name": datastore_type.Value(string_value="nicknameA"),  
            "query_builder": datastore_type.Value(blob_value=b'{"condition":"AND","rules":[{"id":"title","field":"title","type":"string","input":"text","operator":"contains","value":"Boring"}]}')},
          key = {"partition_id":{"project_id":app.config["NDB_PROJECT"]},"path": [
              {"kind": "User", "id": 949}, {"kind": "FilterFeed", "id": 123}]}) 
        self.stub.lookup.set_val(datastore_type.LookupResponse(found=[{"entity":e}]))
        mr = datastore_type.MutationResult(key = {
            "partition_id":{"project_id":"blah"},
            "path": [{"kind": "User", "id": 949}, {"kind": "FilterFeed", "id": 123}]})
        self.stub.commit.set_val(datastore_type.CommitResponse(mutation_results=[mr]))

        r = self.client.post('/v1/949/123/delete')
        
        self.assertEqual(r.status_code, 302)
        # Check the call
        self.stub.commit.assert_called_once()
        commit_req = self.stub.commit.call_args[0][0]
        self.assertEqual(len(commit_req.mutations), 1)
        self.assertTrue(commit_req.mutations[0].delete is not None)
        self.assertEqual(commit_req.mutations[0].delete, e.key)


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
    
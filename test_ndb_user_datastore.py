
import unittest
from unittest import mock

from google.cloud.datastore_v1 import types as datastore_type

import ndb_user_datastore
import ndb_mocks
import model
from app import app

class TestNdbUserDatastore(unittest.TestCase):
    def setUp(self):
        self.ndb_client = ndb_mocks.MockNdbClient()
        self.ndb_patch = mock.patch('google.cloud.ndb.Client',
                new=self.ndb_client)
        self.ndb_patch.start()
        self.addCleanup(self.ndb_patch.stop)
        
        ctxmgr = self.ndb_client().context()
        self.context = ctxmgr.__enter__()
        self.addCleanup(ctxmgr.__exit__, None, None, None)  # TODO: Use enterContext when 3.11 is standard
        
        # needed because flask-security checks app.config
        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)
        
        
    def test_find_user_by_id(self):
        e = datastore_type.Entity(
          properties = {
            "email": {"string_value": "a@b.com"}
            }, 
          key = {
              "partition_id":{"project_id":"blah"}
              ,"path": [{"kind": "User", "id": 123}]})
        b = datastore_type.QueryResultBatch(
            entity_results=[{"entity":e}],
            more_results="NO_MORE_RESULTS",
            entity_result_type="FULL")
        self.ndb_client.stub.run_query.set_val(datastore_type.RunQueryResponse(batch=b))
        
        ds = ndb_user_datastore.NdbUserDatastore(model.User, model.Role)
        user = ds.find_user(id="123")

        self.assertEqual(user.email, "a@b.com")
        self.ndb_client.stub.run_query.assert_called_once()
        self.assertEqual(
            self.ndb_client.stub.run_query.call_args.args[0].query.kind,
            [datastore_type.KindExpression(name="User")])
        self.assertEqual(
            self.ndb_client.stub.run_query.call_args.args[0].query.filter.property_filter,
            datastore_type.PropertyFilter(property={"name": "__key__"},
                                          op="EQUAL",
                                          value={"key_value":{
              "partition_id":{"project_id":"blah"}
              ,"path": [{"kind": "User", "id": 123}]}}))
        
        
    def test_find_user_by_id_NotFound(self):
        b = datastore_type.QueryResultBatch(
            more_results="NO_MORE_RESULTS",
            entity_result_type="FULL")
        self.ndb_client.stub.run_query.set_val(datastore_type.RunQueryResponse(batch=b))
        
        ds = ndb_user_datastore.NdbUserDatastore(model.User, model.Role)
        user = ds.find_user(id="123")

        self.assertIsNone(user)
        self.ndb_client.stub.run_query.assert_called_once()
        self.assertEqual(
            self.ndb_client.stub.run_query.call_args.args[0].query.kind,
            [datastore_type.KindExpression(name="User")])
        self.assertEqual(
            self.ndb_client.stub.run_query.call_args.args[0].query.filter.property_filter,
            datastore_type.PropertyFilter(property={"name": "__key__"},
                                          op="EQUAL",
                                          value={"key_value":{
              "partition_id":{"project_id":"blah"}
              ,"path": [{"kind": "User", "id": 123}]}}))

        
        
    def test_find_user_by_email(self):
        e = datastore_type.Entity(
          properties = {
            "email": {"string_value": "a@b.com"}
            }, 
          key = {
              "partition_id":{"project_id":"blah"}
              ,"path": [{"kind": "User", "id": 123}]})
        b = datastore_type.QueryResultBatch(
            entity_results=[{"entity":e}],
            more_results="NO_MORE_RESULTS",
            entity_result_type="FULL")
        self.ndb_client.stub.run_query.set_val(datastore_type.RunQueryResponse(batch=b))
        
        ds = ndb_user_datastore.NdbUserDatastore(model.User, model.Role)
        user = ds.find_user(email="a@b.com")

        self.assertEqual(user.email, "a@b.com")
        self.ndb_client.stub.run_query.assert_called_once()
        self.assertEqual(
            self.ndb_client.stub.run_query.call_args.args[0].query.kind,
            [datastore_type.KindExpression(name="User")])
        self.assertEqual(
            self.ndb_client.stub.run_query.call_args.args[0].query.filter.property_filter,
            datastore_type.PropertyFilter(property={"name": "email"},
                                          op="EQUAL",
                                          value={"string_value":"a@b.com"}))       
        
    def test_find_user_by_multiple(self):
        e = datastore_type.Entity(
          properties = {
            "email": {"string_value": "a@b.com"}
            }, 
          key = {
              "partition_id":{"project_id":"blah"}
              ,"path": [{"kind": "User", "id": 123}]})
        b = datastore_type.QueryResultBatch(
            entity_results=[{"entity":e}],
            more_results="NO_MORE_RESULTS",
            entity_result_type="FULL")
        self.ndb_client.stub.run_query.set_val(datastore_type.RunQueryResponse(batch=b))
        
        ds = ndb_user_datastore.NdbUserDatastore(model.User, model.Role)
        user = ds.find_user(email="a@b.com", active=True)

        self.assertEqual(user.email, "a@b.com")
        self.ndb_client.stub.run_query.assert_called_once()
        self.assertEqual(
            self.ndb_client.stub.run_query.call_args.args[0].query.kind,
            [datastore_type.KindExpression(name="User")])
        self.assertEqual(
            self.ndb_client.stub.run_query.call_args.args[0].query.filter.composite_filter,
            datastore_type.CompositeFilter(
                op="AND",
                filters=[
                    datastore_type.Filter(property_filter={
                        "property":{"name": "email"},
                        "op":"EQUAL",
                        "value":{"string_value":"a@b.com"}}),
                    datastore_type.Filter(property_filter={
                        "property":{"name": "active"},
                        "op":"EQUAL",
                        "value":{"boolean_value":True}})
                    ]))
                
        
        
    def test_find_user_by_email_NotFound(self):
        b = datastore_type.QueryResultBatch(
            more_results="NO_MORE_RESULTS",
            entity_result_type="FULL")
        self.ndb_client.stub.run_query.set_val(datastore_type.RunQueryResponse(batch=b))
        
        ds = ndb_user_datastore.NdbUserDatastore(model.User, model.Role)
        user = ds.find_user(email="x@x.net")

        self.assertIsNone(user)
        self.ndb_client.stub.run_query.assert_called_once()
        self.assertEqual(
            self.ndb_client.stub.run_query.call_args.args[0].query.kind,
            [datastore_type.KindExpression(name="User")])
        self.assertEqual(
            self.ndb_client.stub.run_query.call_args.args[0].query.filter.property_filter,
            datastore_type.PropertyFilter(property={"name": "email"},
                                          op="EQUAL",
                                          value={"string_value":"x@x.net"}))


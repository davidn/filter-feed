#!/usr/bin/env python3

from unittest import mock

import grpc
from google.cloud.ndb import context

class MockFuture(grpc.Future):
    def __init__(self, val):
        self.val = val
    def add_done_callback(self, fn):
        fn(self)
    def result(self, timeout=None):
        return self.val
    def done(self):
        return True
    def running(self):
        return False
    def cancelled(self):
        return False
    def cancel(self):
        return False
    def traceback(self):
        return None
    def exception(self):
        return None

def MockUnaryUnaryCallable():
        unun = mock.MagicMock(spec=grpc.UnaryUnaryMultiCallable)
        unun.with_call = lambda *args, **kwargs: unun(*args,**kwargs)
        unun.future = lambda *args, **kwargs: MockFuture(unun(*args, **kwargs))
        def set_val(val):
            unun.return_value = val
        unun.set_val = set_val
        def set_side_effect(side_effect):
            unun.side_effect = side_effect
        unun.set_side_effect = set_side_effect
        return unun

def MockDatastoreStub():
    stub = mock.Mock(spec=("lookup", "run_query",  "run_aggregation_query","begin_transaction", "commit","allocate_ids", "rollback",  "reserve_ids",  "delete_operation",  "cancel_operation", "get_operation",  "list_operation"))
    stub.lookup = MockUnaryUnaryCallable()
    stub.run_query = MockUnaryUnaryCallable()
    stub.run_aggregation_query = MockUnaryUnaryCallable()
    stub.begin_transaction = MockUnaryUnaryCallable()
    stub.commit = MockUnaryUnaryCallable()
    stub.rollback = MockUnaryUnaryCallable()
    stub.allocate_ids = MockUnaryUnaryCallable()
    stub.reserve_ids = MockUnaryUnaryCallable()
    stub.get_operation = MockUnaryUnaryCallable()
    stub.list_operations = MockUnaryUnaryCallable()
    stub.delete_operation = MockUnaryUnaryCallable()
    stub.cancel_operation = MockUnaryUnaryCallable()
    return stub

def MockNdbClient():
    client = mock.Mock(spec=("project","namespace","stub", "context"))
    client.project="blah"
    client.namespace=None
    client.stub = MockDatastoreStub()
    client().context = context.Context(client).use
    return client

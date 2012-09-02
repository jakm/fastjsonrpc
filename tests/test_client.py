import os
import sys
sys.path.insert(0, os.path.abspath('..'))

from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred

from fastjsonrpc.client import ReceiverProtocol
from fastjsonrpc.client import StringProducer
from fastjsonrpc.client import Proxy

class TestReceiverProtocol(TestCase):

    def setUp(self):
        self.rp = ReceiverProtocol(Deferred())

    def test_init(self):
        self.assertTrue(isinstance(self.rp.finished, Deferred))

    def test_dataReceivedOnce(self):
        data = 'some random string'

        self.rp.dataReceived(data)
        self.assertEquals(self.rp.body, data)

    def test_dataReceivedTwice(self):
        data1 = 'string1'
        data2 = 'string2'

        self.rp.dataReceived(data1)
        self.rp.dataReceived(data2)
        self.assertEquals(self.rp.body, data1 + data2)

    def test_connectionLostCalled(self):
        data = 'some random string'

        self.rp.dataReceived(data)
        self.rp.connectionLost(None)

        self.assertTrue(self.rp.finished.called)

    def test_connectionLostCalledData(self):
        data = 'some random string'
        self.rp.dataReceived(data)

        def called(data_received):
            self.assertEquals(data_received, data)

        self.rp.finished.addCallback(called)
        self.rp.connectionLost(None)
        return self.rp.finished


class DummyConsumer(object):

    def __init__(self):
        self.body = ''

    def write(self, data):
        self.body += data


class TestStringProducer(TestCase):

    def test_init(self):
        data = 'some random string'
        sp = StringProducer(data)

        self.assertEquals(sp.body, data)
        self.assertEquals(sp.length, len(data))

    def test_startProducing(self):
        data = 'some random string'
        sp = StringProducer(data)

        consumer = DummyConsumer()
        d = sp.startProducing(consumer)

        def finished(_):
            self.assertEquals(consumer.body, data)

        d.addCallback(finished)
        return d


class DummyResponse(object):

    def __init__(self, body):
        self.body = body

    def deliverBody(self, protocol):
        self.protocol = protocol
        self.protocol.dataReceived(self.body)
        self.protocol.connectionLost(None)


class TestProxy(TestCase):

    def test_init(self):
        url = 'http://example.org/abcdef'
        version = '2.0'

        proxy = Proxy(url, version)
        self.assertEquals(proxy.url, url)
        self.assertEquals(proxy.version, version)

    def test_bodyFromResponseProtocolBody(self):
        data = 'some random string'

        proxy = Proxy('', '')
        response = DummyResponse(data)
        d = proxy.bodyFromResponse(response)

        def finished(_):
            self.assertEquals(response.protocol.body, data)

        d.addCallback(finished)
        return d

    def test_bodyFromResponseDeferred(self):
        data = 'some random string'

        proxy = Proxy('', '')
        response = DummyResponse(data)
        d = proxy.bodyFromResponse(response)

        def finished(result):
            self.assertEquals(result, data)

        d.addCallback(finished)
        return d

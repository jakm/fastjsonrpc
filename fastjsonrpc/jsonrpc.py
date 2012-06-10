"""
Copyright 2012 Tadeas Moravec

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

try:
    import cjson as json
except ImportError:
    try:
        import json
    except ImportError:
        try:
            import simplejson as json
        except ImportError:
            raise ImportError('cjon, json or simplejson required')

import random
import types

from zope.interface import implements

from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer
from twisted.python.failure import Failure

VERSION_1 = 1.0
VERSION_2 = 2.0

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

ID_MIN = 1
ID_MAX = 2**31 - 1  # 32-bit maxint

def encodeRequest(method, args, id_=0, version=VERSION_1):
    """
    Returns a JSON object representation of the request.

    @type id_: int or None
    @param id_: request ID. If None, a notification will be sent. If 0 (the
    default), we'll coin some random.

    @type method: str
    @param method: Method name

    @type args: list
    @param args: List of arguments for the method

    @type version: float
    @param version: Which JSON-RPC version to use? Defaults to 1.0

    @return string JSON representation of the request
    """

    request = {}
    request['method'] = method
    request['params'] = args

    if id_ is not None:
        if id_ == 0:
            id_ = random.randint(ID_MIN, ID_MAX)
        request['id'] = id_

    if version == VERSION_2:
        request['jsonrpc'] = '2.0'

    return json.dumps(request)

def decodeResponse(json_response):
    """
    Parses response JSON and returns what the server responded.

    @type json_response: str
    @param json_response: JSON from the server

    @TODO handle exceptions. Create a custom exception for this?
    """

    response = json.loads(json_response)

    if 'result' in response and response['result'] is not None:
        return response['result']

    if 'error' in response and response['error'] is not None:
        raise Exception(response['error'])

    raise ValueError('Not a valid JSON-RPC response')

def decodeRequest(request):
    """
    Decodes the JSON encoded request

    @type request: str
    @param request: The JSON encoded request

    @return dict, containing id, method, params and eventually jsonrpc
    """

    try:
        decoded = json.loads(request)

        assert isinstance(decoded['method'], types.StringTypes), \
                          'Invalid method type: %s' % type(decoded['method'])

        assert isinstance(decoded['params'],
                          (types.ListType, types.TupleType)), \
                          'Invalid params type: %s' % type(decoded['params'])

        # 'jsonrpc' is only contained in V2 requests
        if 'jsonrpc' in decoded:
            assert isinstance(decoded['jsonrpc'],
                              (types.StringTypes, types.FloatType)), \
                              'Invalid jsonrpc type: %s' % \
                                      type(decoded['jsonrpc'])
            decoded['jsonrpc'] = float(decoded['jsonrpc'])
        else:
            decoded['jsonrpc'] = VERSION_1

        # In the case of a notification, there's no id
        if 'id' in decoded:
            assert isinstance(decoded['id'], types.IntType), \
                              'Invalid id type: %s' % type(decoded['id'])

    except ValueError as e:
        raise JSONRPCError(PARSE_ERROR)
    except AssertionError as e:
        raise JSONRPCError(INVALID_REQUEST)

    return decoded

def encodeResponse(result, id_, version):
    """
    Encodes the server response into JSON.

    @type result: mixed
    @param result: What the called function returned. Might be a Failure!

    @type id_: int
    @param id_: the request id

    @type version: float
    @param version: JSON-RPC version

    @return str JSON-encoded response
    """

    def getErrorResponse(result):
        """
        Parses Failure into a dict that can be serialized

        @type result: t.p.f.Failure
        @param result: Failure instance to be parsed

        @return dict that will be serialized
        """

        error_result = {}
        error_result['message'] = str(result.value)

        if isinstance(result.value, TypeError):
            error_result['code'] = INVALID_PARAMS
        else:
            try:
                error_result['code'] = result.value.errno
            except AttributeError:
                error_result['code'] = INTERNAL_ERROR

        try:
            error_result['data'] = result.value.data
        except AttributeError:
            error_result['data'] = None

        return error_result

    if isinstance(result, Failure):
        error_result = getErrorResponse(result)
    else:
        error_result = None

    response = {}
    response['id'] = id_

    if version == VERSION_2:
        response['jsonrpc'] = version

    if error_result:
        response['error'] = error_result
        if version == VERSION_1:
            response['result'] = None
    else:
        response['result'] = result
        if version == VERSION_1:
            response['error'] = None

    return json.dumps(response)

class StringProducer(object):
    """
    There's no FileBodyProducer in Twisted < 12.0.0
    See http://twistedmatrix.com/documents/current/web/howto/client.html for
    details about this class
    """
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class JSONRPCError(Exception):
    """
    JSON-RPC specific error
    """
    def __init__(self, strerr, errno=INTERNAL_ERROR, data=None):
        """
        @type code: int
        @param code: Error code
        """
        self.strerr = strerr
        self.errno = errno
        self.data = data
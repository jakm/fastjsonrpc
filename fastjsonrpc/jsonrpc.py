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


================
JSON-RPC library
================

Provides functions for encoding and decoding the JSON into functions, params
etc. and other JSON-RPC related stuff like constants.
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
    Return a JSON object representation of the request.

    @type id_: int or None
    @param id_: request ID. If None, a notification will be sent. If 0 (the
    default), we'll coin some random.

    @type method: str
    @param method: Method name

    @type args: list
    @param args: List of arguments for the method. Note that packing of the
    arguments is up to the caller!

    @type version: float
    @param version: Which JSON-RPC version to use? Defaults to version 1.

    @rtype: str
    @return: JSON representation of the request
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
    Parse the response JSON and return what the called function returned. Raise
    an exception in the case there was an error.

    @type json_response: str
    @param json_response: JSON from the server

    @rtype: mixed
    @return: What the function returned

    @TODO handle errors properly.
    """

    response = json.loads(json_response)

    if 'result' in response and response['result'] is not None:
        return response['result']

    if 'error' in response and response['error'] is not None:
        raise Exception(response['error'])

    raise ValueError('Not a valid JSON-RPC response')

def decodeRequest(request):
    """
    Decodes the JSON encoded request. Ensures it is valid.

    @type request: str
    @param request: The JSON encoded request

    @rtype: dict
    @return: dict, containing id, method, params and (if present) jsonrpc
    """

    try:
        decoded = json.loads(request)
    except ValueError:
        raise JSONRPCError('Failed to parse JSON', PARSE_ERROR)

    try:

        # 'jsonrpc' is only contained in V2 requests
        if 'jsonrpc' in decoded:
            if not isinstance(decoded['jsonrpc'],
                              (types.StringTypes, types.FloatType)):
                raise JSONRPCError('Invalid jsonrpc type', INVALID_REQUEST)

            decoded['jsonrpc'] = float(decoded['jsonrpc'])
        else:
            decoded['jsonrpc'] = VERSION_1

        if not isinstance(decoded['method'], types.StringTypes):
            raise JSONRPCError('Invalid method type', INVALID_REQUEST)

        if not isinstance(decoded['params'], (types.ListType, types.TupleType)):
            raise JSONRPCError('Invalid params type', INVALID_REQUEST)

    except JSONRPCError as e:
        # Add all known info to the exception, so we can return it correctly

        if 'id' in decoded and 'jsonrpc' in decoded:
            raise JSONRPCError(e.strerror, e.errno, id_=decoded['id'],
                               version=decoded['jsonrpc'])
        elif 'id' in decoded:
            raise JSONRPCError(e.strerror, e.errno, id_=decoded['id'])
        elif 'jsonrpc' in decoded:
            raise JSONRPCError(e.strerror, e.errno, version=decoded['jsonrpc'])
        else:
            raise JSONRPCError(e.strerror, e.errno)

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

    @rtype: str
    @return: JSON-encoded response
    """

    def getErrorResponse(result):
        """
        Parses Failure into a dict that can be serialized

        @type result: t.p.f.Failure
        @param result: Failure instance to be parsed

        @rtype: dict
        @return: dict that can be serialized to JSON
        """

        error_result = {}
        try:
            error_result['message'] = str(result.value.strerror)
        except AttributeError:
            error_result['message'] = str(result.value)

        if isinstance(result.value, TypeError):
            error_result['code'] = INVALID_PARAMS
        else:
            try:
                error_result['code'] = result.value.errno
            except AttributeError:
                error_result['code'] = INTERNAL_ERROR

        try:
            if result.value.data is not None:
                error_result['data'] = result.value.data
        except AttributeError:
            pass

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


class JSONRPCError(Exception):
    """
    JSON-RPC specific error

    @TODO str, repr etc.?
    """
    def __init__(self, strerror, errno=INTERNAL_ERROR, data=None, id_=None,
                 version=VERSION_1):
        """
        @type strerror: str
        @param strerror: Description of the error

        @type errno: int
        @param errno: Error code

        @type data: mixed
        @param data: Whatever additional data we want to pass
        """
        self.strerror = strerror
        self.errno = errno
        self.data = data
        self.id_ = id_
        self.version = version

# -*- coding: utf-8 -*-
# ===================================================================
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  
#      http://www.apache.org/licenses/LICENSE-2.0
#  
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  
# ===================================================================
import json
import pandas as pd
from zoomdata.src.rest import RestCalls
from zoomdata.src.datatypes import Filter, TimeFilter

rest = RestCalls()

class RawData(object):
    """
    Returns the raw data from the specified source as a pandas dataframe object.
    """

    def __repr__(self):
        return """To execute this please add brackets at the end of the expression () or append .execute()"""

    def __init__(self, init_data, limit=10000):
        self.__data = init_data
        self.__filters  = []
        self.__fields   = []
        self.__exclude  = []
        self.__time     = {}
        self.__limit    = limit
        self.__error    = False
        self.__print_ws_requests = False

    def __clear_attrs__(self):
        self.__filters  = []
        self.__fields   = []
        self.__exclude  = []
        self.__time     = {}
        self.__limit    = 10000
        self.__error    = False
        self.__print_ws_requests = False

    def __call__(self):
        return self.execute()

    def _wsrequest(self):
        self.__print_ws_requests = True
        return self

    def fields(self, *args):
        if isinstance(args[0], list):
            self.__fields = args[0]
        elif isinstance(args[0], str):
            self.__fields = list(args)
        else:
            print('Incorrect parameter for fields()')
            self.__error = True
        return self

    def rows(self, rows):
        if not isinstance(rows, int):
            print('Row is not a number')
            self.__error = True
        self.__limit = rows
        return self

    def exclude(self, *args):
        if isinstance(args[0], list):
            self.__exclude = args[0]
        elif isinstance(args[0], str):
            self.__exclude = list(args)
        else:
            print('Incorrect parameter for exclude()')
            self.__error = True
        return self

    def time(self, time):
        if not isinstance(time, TimeFilter):
            print("Time parameter should be TimeFilter object")
            self.__error = True
            return self
        self.__time = time.getval()
        return self

    def filter(self, *args):
        filters = args
        if isinstance(args[0], list):
            filters = args[0]
        for f in filters:
            if not isinstance(f, Filter):
                print('Filter parameters must be a Filter object')
                self.__error = True
                return self
        self.__filters = [f.getval() for f in filters]
        return self

    def execute(self):
        if self.__error:
            self.__clear_attrs__()
            return False
        server_url = self.__data['url']
        headers = self.__data['headers']
        source_id = self.__data['source_id']
        source_key = self.__data['source_key']

        try:
            import ssl
            from websocket import create_connection
            # Parse the fields in case they are for the not visual
            fields = self.__fields
            vis = rest.getSourceById(server_url, headers, source_id)
            if not vis: 
                return False
            fields = self.__fields if self.__fields else [f['name'] for f in vis['objectFields']]
            # Exclude fields:
            [fields.remove(f) for f in self.__exclude if f in fields]

            socketUrl = server_url + "/websocket?key=" + source_key
            socketUrl = socketUrl.replace('https','wss')
            start_vis = {
                         "api": "VIS",
                         "cid": "f3020fa6e9339ee5829f6e2caa8d2e40",
                         "type": "START_VIS",
                         "aggregate": False,
                         "sourceId": source_id,
                         "limit": self.__limit,
                         "filters": self.__filters,
                         "fields": fields
            }
            if self.__time:
                start_vis.update({'time':self.__time})
            #If requested, print the request
            if self.__print_ws_requests:
                print(socketUrl)
                print('====================')
                print('      START_VIS     ')
                print('====================')
                print(json.dumps(start_vis))
            #Clean all attributes
            self.__clear_attrs__()
            # WS request
            ws = create_connection(socketUrl)
            ws.send(json.dumps(start_vis))
            req_done = False
            dataframe = []
            maxloop = 0
            while maxloop <= 30:
                frame = ws.recv() #NOTE: This will hang if no data is received
                if 'NOT_DIRTY_DATA' in frame:
                    ws.close()
                    break
                if 'INTERNAL_ERROR' in frame:
                    ws.close()
                    print('An error occured:')
                    frame = json.loads(frame)
                    if frame.get('details',False):
                        print(frame['details'])
                    else: 
                        print(frame)
                    return False
                maxloop += 1
                frame = json.loads(frame)
                dataframe.extend(frame.get('data',[]))

            #Parsing takes a little more due to they're different for each visuals
            if maxloop == 30: # There was an error
                ws.close()

            if dataframe:
                #Parse the right field type
                dataframe = pd.DataFrame(dataframe, columns=fields)
                for f in vis['objectFields']:
                    if f['name'] in fields and f['type'] == 'TIME': 
                        dataframe[f['name']] = pd.to_datetime(dataframe[f['name']])
                return dataframe
            print('No data was returned')
            return False

        except ImportError:
            print ('No websocket module found. Install: pip3 install websocket-client')

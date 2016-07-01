import urllib3
import json
from urllib.parse import quote
http = urllib3.PoolManager()

def data(resp):
    return resp.data.decode('ascii')

class RestCalls(object):

    def createConnection(self, url, headers, accountID, connReq, connectionName):
        connReq['mongo']['name'] = connectionName
        body=json.dumps(connReq['mongo'])
        service = '/api/accounts/'+accountID+'/connections'
        print('Creating connection...')
        r = http.request('POST', url+service ,headers=headers, body=body)
        if r.status in [200, 201]:
            print('Connection created')
            return data(r)
        else:
            print(data(r))
        return False

    def createSource(self, url, headers, accountID, sourceName, connectionName, connReq, sourceReq):
        # Try to get the connection first in case it exists
        service = '/api/accounts/'+accountID+'/connections/name/'+connectionName
        r = http.request('GET', url+service, headers=headers)
        if r.status in [200]:
            connResponse = data(r)
        elif r.status in [403, 404]:
            connResponse = self.createConnection(url, headers, accountID, connReq, connectionName)
        else:
            print(data(r))
            return False
        # If a valid connection response is available
        if connResponse:
            links = json.loads(connResponse)['links']
            url = False
            url = [l['href'] for l in links if l['rel'] == 'sources']
            if url:
                print('Good Url')
                sourceReq['name'] = sourceName
                sourceReq['sourceParameters']['collection']= sourceName;
                body=json.dumps(sourceReq)
                print('Creating source...')
                r = http.request('POST', url[0], headers=headers, body=body)
                if r.status in [200, 201]:
                    print('Source created')
                    return True
                else:
                    print(data(r))
        return False

    def getUserAccount(self, url, headers, user):
        service = '/api/users/username/'+user
        r = http.request('GET', url+service ,headers=headers)
        if r.status in [200]:
            resp= json.loads(data(r))
            href = [l['href'] for l in resp['links'] if l['rel'] == 'account']
            # https://server:port/zoomdata/api/accounts/56e9669ae4b03818a87e452c
            return href[0].split('/')[-1]
        print(data(r))

    def getSourcesByAccount(self, url, headers, accountID):
        service = '/api/accounts/'+accountID+'/sources'
        r = http.request('GET', url+service ,headers=headers)
        resp= json.loads(data(r))
        resp = resp.get('data',False)
        sources = []
        if resp:
            count = 1
            for d in resp:
                print(str(count) +'. '+d['name'])
                count += 1
        else: 
            print(resp)

    def getVisualizationsList(self, url, headers):
        """ Get the list of all visualizations allowed by Zoomdata """
        service = '/service/visualizations'
        r = http.request('GET', url+service, headers=headers)
        if r.status in [200]:
            vis = [{'id': d['id'], 'name': d['name']} for d in json.loads(data(r))]
            return vis
        print(data(r))
        return False

    def getSourceById(self, url, headers, sourceId):
        service = '/service/sources/'+sourceId
        r = http.request('GET', url+service, headers=headers)
        if r.status in [200]:
            return json.loads(data(r))
        print(data(r))
        return False

    def getSourceKey(self, url, headers, sourceName, print_error=True, token=False):
        # This method will be useless once oauth be implemented
        service = '/service/sources/key?source='+sourceName.replace(' ','+')
        if token:
            service += '&access_token='+token
        r = http.request('GET', url+service ,headers=headers)
        if r.status in [200]:
            resp = json.loads(data(r))
            return resp['id']
        if print_error:
            print(data(r))
        return False

    def getSourceID(self, url, headers, accountID, sourceName, printError = True):
        # https://pubsdk.zoomdata.com:8443/zoomdata/api/accounts/56e9669ae4b03818a87e452c/sources/name/Ticket%20Sales
        service = '/api/accounts/'+accountID+'/sources/name/'+sourceName.replace(' ','%20')
        r = http.request('GET', url+service, headers=headers)
        if r.status in [200]:
            resp= json.loads(data(r))
            href = [l['href'] for l in resp['links'] if l['rel'] == 'self']
            # https://server:port/zoomdata/api/sources/
            return href[0].split('/')[-1]
        if printError:
            print(data(r))
        return False
    
    def createSourceFromData(self, url, headers, accountId, sourceName, df, urlParams={}):
        # Creates or uses a source to populate it with data (from a dataframe or file without creating collections)
        # Check if the source exists
        sourceId = self.getSourceID(url, headers, accountId, sourceName, printError=False)
        if not sourceId:
            print('Creating source "'+sourceName+'"...')
            service = '/api/accounts/'+accountId+'/sources/file'
            body = {'name': sourceName, 'sourceParameters':{}}
            #Create the source
            #https://pubsdk.zoomdata.com:8443/zoomdata/api/accounts/56e9669ae4b03818a87e452c/sources/file
            r = http.request('POST', url+service, headers=headers, body=json.dumps(body))
            if r.status in [200, 201]:
                resp = json.loads(data(r))
                href = [l['href'] for l in resp['links'] if l['rel'] == 'self']
                # https://server:port/zoomdata/api/sources/
                sourceId = href[0].split('/')[-1]
                print('Source with id "'+sourceId+'" sucessfully created')
            else:
                print(data(r))
                return False
        #Populate the source with the specified data
        print('Populating source with data...')
        service='/api/sources/'+sourceId+'/data?'
        param_format = '%s=%s'
        params_list = []
        for param in urlParams:
            p = param_format % (param, quote(urlParams[param]))
            params_list.append(p)
        service += '&'.join(params_list)
        r = http.request('PUT', url+service, headers=headers, body=df)
        if r.status in [200, 201]:
            print('Done!')
            return True
        print(data(r))
        return False

    def updateSourceDefinition(self, url, headers, sourceId, body):
        service = '/service/sources/'+sourceId
        body=json.dumps(body)
        r = http.request('PATCH', url+service, headers=headers, body=body)
        if r.status in [200]:
            return True
        print(data(r))
        return False

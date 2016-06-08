#/usr/bin/python3
import os
import urllib3
import json
import base64
from .rest import RestCalls
from .visdefinition import VisDefinition
from .config import *
from .jsbuilder import JSBuilder
from .templates import Template
from IPython.display import HTML

http = urllib3.PoolManager()
rest = RestCalls()
vd = VisDefinition()
js = JSBuilder()
t = Template()
deps = ['ZoomdataSDK','jquery']

def data(resp):
    return resp.data.decode('ascii')

class ZDVisualization(object):

    """ ZDVisualization puts together all the javascript pieces
    needed to create a connection with the ZD SDK and fecth 
    the requested data. It finally renders the html and js into
    the notebook output dom through the HTML object """

    def __init__(self):
        """ To ensure maximum flexibility for the visualization configuration
        here must be setted all values that may change """
        #Main configurations
        self._conf = config
        protocol = 'https' if config['secure'] else 'http'
        self._serverURL = '%s://%s:%s%s' % (protocol, config['host'], config['port'], config['path'])
        self._sourceCredentials = {}
        if os.path.exists('data/sources.json'):
            with open('data/sources.json','r') as sc:
                self._sourceCredentials = json.load(sc)

        #Visualization
        self.connResp = {}
        self._width = 800
        self._height = 400
        self._renderCount = 0 #To render a different chart each time
        self._paths = paths
        self._query = queryConfig
        self._credentials = ''  # This is the key to get the source key to get the visualization
        self._source_obj_credentials = '' # This is the source id to get the source definition
        self.__source_charts = [] # Active visualizations for the current source
        self.__allowedVisuals = [] # All the visualizations names allowed by zoomdata
        self._source = ''
        self._chart = chart
        self._variables = {}
        self._metric = metric
        self._group = groups
        self._filters = []
        self._metricParams = metricParams
        self._groupParams = groupParams

        #Attrs for new source/collection creation
        self._connReq = connReq
        self._sourceReq = sourceReq

    def auth(self, user, password):
        cred = user+':'+password
        key = base64.b64encode(cred.encode('ascii'))
        key = 'Basic ' + key.decode('ascii')
        self._connReq['mongo']['created']['by']['username'] = user
        self._sourceReq['created']['by']['username'] = user
        self._conf['headers']['Authorization'] = key

    def __createMongoCollection(self, name, df, connName):
        """ Creates a MongoDB collection """
        try:
            from pymongo import MongoClient
            client = MongoClient(self._conf['mongoServer'], self._conf['mongoPort'] )
            db = getattr(client, self._conf["mongoSchema"])
            collection = db[name] 
            if df: # Use the dataframe if it is specified
                print('Creating collection '+name+'...')
                collection.insert_many(df)
                print('collection created on db')
            print('creating data source using collection '+name+'...')
            return rest.createSource(self._serverURL, self._conf['headers'], \
                                     self._conf['accountID'], name, connName, 
                                     self._connReq, self._sourceReq)
        except ImportError:
            print ('To create mongo collections you must have the pymongo module installed')
        except Exception as e:
            print('Error: '+str(e))


    def createSource(self, sourceName, dataframe=False, handler='mongo', connName=False): 
        """Creates a new Zoomdata collection using the specified parameters:
                Parameters:
                    sourceName: The name given for the new source
                    dataframe: Contains the data used to populate the source, if it is not specified
                               then a collection with name sourceName will be used instead
                    handler: The store handler, 'mongo' is used by default
                    connName: The name of the connection, if no name is specified, the source name will be used.
        """
        if(self._conf['headers']['Authorization']):
            if handler in ['mongo','spark']:
                if handler == 'mongo':
                    connName = connName or sourceName
                    return self.__createMongoCollection(sourceName, dataframe, connName)
            else:
                print('Invalid collection handler!')
        else:
            print('You need to authenticate: ZD.auth("user","password")')

    def listSources(self):
        """ List the availables sources for the account specified in ZD.conf["accountID"] """
        if(self._conf['headers']['Authorization']):
            rest.getSourcesByAccount(self._serverURL, self._conf['headers'], self._conf['accountID'])
        else:
            print('You need to authenticate: ZD.auth("user","password")')
            
    def __setRequireConf(self):
        #Set the require configuration part
        return 'require.config({paths:%s});' % js.s(self._paths)

    def __getJSTools(self):
        tools = ''
        path = os.path.dirname(os.path.realpath(__file__))
        with open(path+'/js/tools.js') as t: #Set of functions used within the script
            tools = ''.join(t.readlines())
        return tools

    def __getPickers(self):
        opt = t.optionFmt % ('','Select option')
        dim = t.selectFmt % ('Dimension', self._groupParams['name'], opt)
        met = t.selectFmt % ('Metric', self._metricParams['name'], opt)
        return t.divFilters % (dim + met)

    def __createClient(self):
        credentials = {
                'credentials': {'key': self._credentials},
                'application': {'secure': self._conf['secure'], 
                                'host': self._conf['host'], 
                                'port': self._conf['port'], 
                                'path': self._conf['path']}
                }
        params = js.s(credentials)
        return 'ZoomdataSDK.createClient(%s)' % (params)

    def __connectionPromise(self):
        """Returns the string associated to the 
        promise that connects with ZD and creates the visualization"""
        prom = self.__createClient()
        p ='window.client = client; return(client)'
        then = '.then(%s)' % (js.createFunc(params='client',body=p, anon=True))
        visualconf = {'element':'%s', 'config': self._query}
        visualconf.update( { 'source': {'name': self._source},
                             'visualization': self._chart,
                             'variables': self._variables
                           })
        p = js.s(visualconf)
        p = js.setVars(p, 'visLocation') #set the element for echarts rendering

        # The function .done is where the Thread object is created
        # and the specific data such as groups, variables, parameters,
        # etc for the specific visualization being loaded
        doneBody = t.doneBody % {'met': self._metricParams['name'], 'dim': self._groupParams['name'] }
        done = '.done(%s);' % (js.createFunc(params='result',body=doneBody, anon=True))
        p = 'client.visualize(%s)%s' % (p, done)
        then1 = '.then(%s);' % (js.createFunc(params='client',body=p, anon=True))
        return prom+then+then1

    def __wrapper(self):
        """Wraps and render all the JS code inside the require module"""
        tools = self.__getJSTools()
        visualDiv = 'visual%s' % (str(self._renderCount))
        varKernel = js.var('kernel','IPython.notebook.kernel')
        varChart = js.var('chart',js.s(self._chart))
        visLocation = js.var('visLocation','document.getElementById("'+visualDiv+'")')
        varFilters  = js.var('filters', '[]')
        #These two variables hold the selected metric and dimensions objects
        varMetric   = js.var(self._metricParams['name'], js.s(self._metric))
        varGroup    = js.var(self._groupParams['name'], js.s(self._group))
        #The promise with the SDK connection code
        zdSDK = self.__connectionPromise()
        #. Jquery onchange handlers for the pickers
        metricJS = t.metricFilter % self._metricParams
        dimensionJS = t.groupFilter %  self._groupParams
        # wrap everything up as the require callback body
        cb = tools + visLocation + varFilters + varChart + varMetric \
            + varGroup + zdSDK + metricJS + dimensionJS
        reqCallback = js.createFunc(params=deps, body=cb, anon=True)
        return 'require(%s,%s)' % (js.s(deps), reqCallback)

    def __getVisualization(self):
        """Set up of the final code snippet to be rendered"""
        w, h = self._width, self._height
        visualDiv = 'visual%s' % (str(self._renderCount))
        pickers = ''
        if self._chart not in ['Map: Markers']:
            pickers = self.__getPickers()
        htmlcode = pickers + t.loadmsg + t.divChart % (visualDiv, str(w), str(h))
        jscode = t.scriptTags % (self.__setRequireConf(), self.__wrapper())
        html = htmlcode + jscode
        iframe = t.iframe % (t.requirejs, html, str(w+40), str(h+80) )
        return iframe, htmlcode, jscode

    def render(self):
        """ Renders a visualization from Zoomdata. Takes in count the ZD object attributes such as
        chart, source, etc. to render an specific visualization """
        if(self._source):
            iframe = self.__getVisualization()[0]
            self._renderCount += 1
            return HTML(iframe)
        else:
            print('You need to specify a source: ZD.source = "Source Name"')
        # return HTML(html + jscode)

    def __getHTML(self):
        try:
            import jsbeautifier
            from bs4 import BeautifulSoup as bs
            iframe, html, jscode = self.__getVisualization()
            soup=bs(html,"lxml")
            html=soup.prettify()
            jscode = jsbeautifier.beautify(jscode)
            print (html+'\n'+jscode)
        except ImportError:
            print ('Modules jsbeautifier and beautifulsoup4 are required for this feature')

    #====== SET CHART TYPES FOR A VISUALIZATION IF IT DOES NOT HAVE IT ==========
    def setVisualization(self, name, definition={}):
        if(self._conf['headers']['Authorization']):
            # 1. First get the ID of the specific visualization
            if self._credentials:
                print('Checking allowed chart types...')
                if not (self.__allowedVisuals):
                    self.__allowedVisuals = rest.getVisualizationsList(self._serverURL, self._conf['headers'])
                visualsNames = [v['name'] for v in self.__allowedVisuals]
                if name not in visualsNames:
                    print('Visualization type not found or not configured. Supported visualizations are:')
                    print('\n'.join(visualsNames))
                else:
                    visId = [v['id'] for v in self.__allowedVisuals if v['name'] == name]
                    result = vd.setMapMarkers(visId[0], definition, self._serverURL, \
                                                self._conf['headers'], self._source_obj_credentials)
                    if result:
                        self.__source_charts.append(name)
            else:
                print('You must define a source before setting a new visualization')
        else:
            print('You need to authenticate: ZD.auth("user","password")')

            
    #====== PROPERTIES (DEFINED THIS WAY TO PROVIDE DOCSTRING) ===============
    @property
    def chart(self):
        """String: The chart types for the visualization. Allowed values are:
            Donut, Bars, Pie, KPI, Scatter Plot, Floating Bubbles, Packed Bubbles,
            Tree Map, Heat Map, Word Cloud
        """
        return self._chart

    @chart.setter
    def chart(self, value):
        if(self._conf['headers']['Authorization']):
            if not self._source:
                print('You need to define a source before setting the chart')
            else:
                if not (self.__allowedVisuals):
                    self.__allowedVisuals = rest.getVisualizationsList(self._serverURL, self._conf['headers'])
                visualsNames = [v['name'] for v in self.__allowedVisuals]
                if value in visualsNames: # If is an allowed visualization type
                    if value in self.__source_charts: # If is an active visualization for the source
                        self._chart = value
                    else:
                        print('Chart type not configured, to configure it use ZD.setVisualization method')
                else:
                    print('Chart type not found. Supported charts are:')
                    print('\n'.join(visualsNames))
        else:
            print('You need to authenticate: ZD.auth("user","password")')

    @property
    def width(self):
        """ Integer: The width of the visualization """
        return self._width

    @width.setter
    def width(self, value):
        self._width = value

    @property
    def height(self):
        """ Integer: The height of the visualization """
        return self._height

    @height.setter
    def height(self, value):
        self._height = value

    # @property
    # def paths(self):
        # return self._paths

    # @paths.setter
    # def paths(self, value):
        # self._paths = value

    @property
    def query(self):
        """
        Dictionary. Allows to manually modify the query used to fecth data from ZD. 
        """
        return self._query

    @query.setter
    def query(self, value):
        self._query = value

    @property
    def source(self):
        """ The source used to fetch and render the visualization """
        return self._source

    @source.setter
    def source(self, value):
        credentials = ''
        if self._sourceCredentials.get(value, False):
            self._credentials = self._sourceCredentials[value][0]
            self._source_obj_credentials = self._sourceCredentials[value][1]
            self._source = value
            if not self.__source_charts:
                vis = rest.getSourceById(self._serverURL, self._conf['headers'], self._source_obj_credentials)
                self.__source_charts = [v['name'] for v in vis['visualizations']]
        else:
            if(self._conf['headers']['Authorization']):
                service = '/service/sources/key?source='+value.replace(' ','+')
                url = 'https://%s:%s%s' % (self._conf['host'], self._conf['port'], self._conf['path'])
                r = http.request('GET', url+service ,headers=self._conf['headers'])
                resp = json.loads(data(r))
                failed = False
                if resp.get("error", False):
                    failed = True
                    print (r.data)
                if resp.get("details", False):
                    failed = True
                    print ("Incorrect source name")
                if not failed:
                    self._credentials = resp['id']
                    self._source_obj_credentials = resp['objectIds'][0] # TODO: Check on this because this is a list of ?
                    self._source = value
                    self._sourceCredentials.update({value: [ self._credentials, self._source_obj_credentials ]})
                    if not self.__source_charts:
                        vis = rest.getSourceById(self._serverURL, self._conf['headers'], self._source_obj_credentials)
                        self.__source_charts = [v['name'] for v in vis['visualizations']]
                    with open('data/sources.json', 'w') as sc:
                        json.dump(self._sourceCredentials, sc)
            else:
                print('You need to authenticate: ZD.auth("user","password")')

    @property
    def variables(self):
        """ String: Representation of a JSON """
        return self._variables

    @variables.setter
    def variables(self, value):
        self._variables = value

    @property
    def metric(self):
        """ Dict: Represent the metric used to render the visualization. Can be visually changed through drop-downs"""
        return self._metric

    @metric.setter
    def metric(self, value):
        self._metric = value

    @property
    def group(self):
        """ Dict: Represent the dimension used to render the visualization. Can be visually changed through drop-downs"""
        return self._group

    @group.setter
    def group(self, value):
        self._group = value

    @property
    def conf(self):
        """Dict: Configuration to create collections and sources. Uses specific Zoomdata configuration such as port and server for mongo connections, accounts Ids, authorization headers
        """
        return self._conf

    @conf.setter
    def conf(self, value):
        self._conf = value
        protocol = 'https' if self._conf['secure'] else 'http'
        self._serverURL = '%s://%s:%s%s' % (protocol, self._conf['host'], self._conf['port'], self._conf['path'])

    @property
    def connReq(self):
        """ Dict: Specific data for store handlers as mongo, spark, etc. """
        return self._connReq

    @connReq.setter
    def connReq(self, value):
        self._connReq = value

    @property
    def sourceReq(self):
        """
        Dict Specific data for source creation. Allows to add description to the source being created.
        """
        return self._sourceReq

    @sourceReq.setter
    def sourceReq(self, value):
        self._sourceReq = value




        
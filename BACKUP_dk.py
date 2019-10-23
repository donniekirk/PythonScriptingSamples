# coding utf-8
import json, urllib, httplib
import sys
import argparse
import urlparse
import os
import ssl

# Check if SSL verification needs to be disabled
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify SSL certificates by default
    pass
else:
    # Disable SSL verficiation
    ssl._create_default_https_context = _create_unverified_https_context

IN_WINE = any(e in os.environ for e in ('WINELOADERNOEXEC',
                                        'DOTWINE',
                                        'WINEPREFIX',
                                        'WINEDEBUG'))
PROG_NAME = os.path.basename((sys.argv[0]
                              if not IN_WINE
                              else os.path.splitext(sys.argv[0])[0]))
                                        
backup_args = argparse.ArgumentParser(prog=PROG_NAME, description='Creates a backup of the site configuration by taking the following command line arguments. If the command line arguments are not passed, the backup utility switches to the interactive mode.')

backup_args.add_argument('-s', '--site', 
    required=True,
    default=None,
    help='Description: Site URL in the format http(s)://<host>:<port>/arcgis')
backup_args.add_argument('-u', '--username', 
    required=True,
    default=None,
    help='Description: Name of a user with administrative privileges to the site')
backup_args.add_argument('-p', '--password', 
    required=True,
    default=None,
    help='Description: Password of the user specified in the -u parameter')
backup_args.add_argument('-f', '--folder', 
    required=True,
    default=None,
    help='Description: Absolute path to the folder that will hold the backup file. The ArcGIS Server account must have write access to this folder.')

backup_args._optionals.title = "Arguments"

def backup():
    
    if (len(sys.argv) > 1): #at lease one command line argument is passed
        args = backup_args.parse_args()
        site = 'https://localhost:6443/arcgis'
        username = 'siteadmin'
        password = 'g!sc0lorado'
        folder = '//Server//GIS-GCDP//GCDP//Workspaces//DK'
    else: # no command line arguments have been passed, so switching to interactive mode
        print "No parameters provided. Switching to interactive mode..."
        print
        #site = raw_input("Enter site URL in the format http(s)://<host>:<port>/arcgis: ")
        site = 'https://localhost:6443/arcgis'
        username = 'siteadmin'
        #username = raw_input("Enter user name: ")
        #password = raw_input("Enter password: ")
        password = 'g!sc0lorado'
        #folder = raw_input("Enter the absolute path to the folder that will hold the backup file: ")
        folder = '//Server/GIS-GCDP/ArcServer_Backups/Secure/Primary'
    protocol, serverName, serverPort, context = splitSiteURL(site)
    if (serverName == None or serverPort == None or protocol == None or context == None):
        return -1
    
    if not context.endswith('/'):
        context += '/'
    
    if not context.endswith('admin/'):
        context += 'admin/'
        
    tokenURL = context+"generateToken"
    token = getToken(serverName, serverPort, protocol, tokenURL, username, password)
    
    if token == None:
        return -1
                    
    #Create a backup of the site
    backupURL = context+"exportSite"
    
    folder = folder.decode(sys.stdin.encoding).encode('utf-8')
    params = urllib.urlencode({'token': token, 'f': 'json', 'location': folder})

    print "Backing up the site running at \"" + serverName +"\""
    
    try:
        response, data = postToServer(serverName, serverPort, protocol, backupURL, params)
    except:
        print "Unable to connect to the ArcGIS Server site on " + serverName + ". Please check if the server is running."
        return -1     
    
    if (response.status != 200):
        print "Unable to back up the site running at " + serverName
        print str(data)
        return -1
    
    if (not assertJsonSuccess(data)):
            print "Unable to back up the site running at " + serverName
    else:
            dataObj = json.loads(data)
            print "Site has been successfully backed up and is available at this location: " + dataObj['location'] 

def splitSiteURL(siteURL):

    try:
        serverName = ''
        serverPort = -1
        protocol = 'http'
        context = '/arcgis'
        urllist = urlparse.urlsplit(siteURL)
        d = urllist._asdict()
        
        serverNameAndPort = d['netloc'].split(":")
        
        if (len(serverNameAndPort) == 1): # user did not enter the port number, so we return -1
            serverName = serverNameAndPort[0]
        else:
            if (len(serverNameAndPort) == 2):
                serverName = serverNameAndPort[0]
                serverPort = serverNameAndPort[1]
       
        if (d['scheme'] is not ''):
            protocol = d['scheme']
        
        if (d['path'] is not '/' and d['path'] is not ''):
            context = d['path']

        return protocol, serverName, serverPort, context  
    except:
        print "The site URL should be in the format http(s)://<host>:<port>/arcgis"
        return None, None, None, None
        
# A function that will post HTTP POST request to the server
def postToServer(serverName, serverPort, protocol, url, params):
    
    if (serverPort == -1 and protocol == 'http'):
        serverPort = 80
    
    if (serverPort == -1 and protocol == 'https'):
        serverPort = 443
        
    if (protocol == 'http'):
        httpConn = httplib.HTTPConnection(serverName, serverPort)

    if (protocol == 'https'):
        httpConn = httplib.HTTPSConnection(serverName, serverPort)
        
    headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain",'referer':'backuputility','referrer':'backuputility'}
     
    # URL encode the resource URL
    url = urllib.quote(url.encode('utf-8'))
    
    # Build the connection to add the roles to the server
    httpConn.request("POST", url, params, headers)

    response = httpConn.getresponse()
    data = response.read()
    httpConn.close()

    return (response, data)

def getToken(serverName, serverPort, protocol, tokenURL, username, password):
    
    params = urllib.urlencode({'username': username.decode(sys.stdin.encoding).encode('utf-8'), 'password': password.decode(sys.stdin.encoding).encode('utf-8'),'client': 'referer','referer':'backuputility','f': 'json'})
    
    try:
        response, data = postToServer(serverName, serverPort, protocol, tokenURL, params)
    except:
        print "Unable to connect to the ArcGIS Server site on " + serverName + ". Please check if the server is running."
        return None    
          
    if (response.status != 200):
        print "Error while generating the token."
        print str(data)
        return None
    if (not assertJsonSuccess(data)):
        print "Error while generating the token. Please check if the server is running and ensure that the username/password provided are correct."
        return None
    else: 
        # Extract the token from it
        token = json.loads(data)   
        return token['token']       

# A function that checks that the input JSON object
#  is not an error object.
def assertJsonSuccess(data):
    obj = json.loads(data)
    if 'status' in obj and obj['status'] == "error":
        if ('messages' in obj):
            errMsgs = obj['messages']
            for errMsg in errMsgs:
                print
                print errMsg
        return False
    else:
        return True


if __name__ == '__main__':
    sys.exit(backup())

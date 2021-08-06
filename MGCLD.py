import os
import shutil
import inspect
import MGComm
import sys
import re
import string
import time
import logging
from time import sleep, ctime
import cmd
from cmd import Cmd
import MGTest

'''
This is a class library for the "content director"
It's methods provide the functionality:
    to get/set the device configuration
    to monitor the logs
    to perform tasks on the device
'''

class ScriptError(SyntaxError):
    pass

class MGCLD(object):
    'MGCLD class - creates a CLD object containing the device configuration and ssh session
    an ssh session'
    def __init__(self,opts,testinfo):
        if 'ip' not in opts:
            raise ScriptError, "ip address is required in opts dictionary", None
        for item in opts:
            setattr(self,item,opts[item])
        testlog = logging.getLogger('mgtest')
        testlog.debug("started " + opts['ip'])
        testlog.debug("calling MGComm.getssh for " + opts['ip'])
        self.testlog = testlog
        ssh = MGComm.getssh(opts)
        self.ssh = ssh
        if 'error' in opts:
            raise ScriptError, "MGCLD init: unable to ssh to " + opts['ip'] + ": " \
                + opts['error']
            return
        self.testinfo = testinfo
        testlog.debug("calling GetConfiguration for " + opts['ip'])
        self.GetConfiguration()

    def GetConfiguration(self):
        '''TODO: find way to call function as a variable then do this in a loop'''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug(" starting")
        hostname = self.GetHostName()
        setattr(self,'hostname',hostname)
        if self.testinfo.error:
            return -1
        setattr(self,'hostname',hostname)
 
        vinfo = self.GetSoftwareVersion();
        if not self.testinfo.error:
            setattr(self,"version",vinfo)
        else:
            return -1
         
        sinfo = self.GetCLDStatus();
        if not self.testinfo.error:
            setattr(self,"status",sinfo)
        else:
            return -1
        
        configvalues = self.GetConfigValues()
        setattr(self,"cldconfig",configvalues)
        return 0
    
    def GetConfigLimits(self):
        '''
        # Method: GetConfigLimits
        # Scope: PUBLIC
        # Status: Complete
        # Description: parse the ssmd and mdscore config files in /anonymous/config/
        #   to obtain the config limits configured for the cld.
        # Input Parameters
        #  self - REQUIRED - the ContentDirector object
        # Output: returns -1 if error (reports the error)
        # configlimits - hash containing config limit values
        # configlimits['slicecount'] - maximum number of unique slices
        # configlimits['memorylimit'] - maximum amount of dynamic memory that can be used
        # configlimits['nodescount'] - maximum number nodes (files+dirs+hardlinks)
        # configlimits['filescount'] - maximum number files
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        configlimits = {
            'sliceCountMax' : 0,
            'memory_limit': 0,
            'nodes_count': 0,
            'files_count': 0,
            }
        files = ['/anonymous/config/mdscore',
                 '/anonymous/config/mdscore-local',
                 '/anonymous/config/ssm',
                 '/anonymous/config/ssm-local'
                ]
        command = "cat "
        for myfile in files:
            mycommand = command + myfile
            output,error = MGComm.sendsshcmd(self.ssh,mycommand)
            if error:
                self.testlog.error(error)
                return -1
            for line in output:
                m = re.match("\s*\#",line)
                if m: continue
                if 'ssm' in myfile:
                    m = re.search("sliceCountMax\s(\d*)",line)
                    if m:
                        configlimits['sliceCountMax'] = m.groups()[0]
                        continue
                else:
                    m = re.search("nodes_count = (\d*)",line)
                    if m:
                        configlimits['nodes_count'] = m.groups()[0]
                        continue
                    m = re.search("memory_limit = (\d*)",line)
                    if m:
                        configlimits['memory_limit'] = m.groups()[0]
                        continue
                    m = re.search("files_count = (\d*)",line)
                    if m:
                        configlimits['files_count'] = m.groups()[0]
                        continue
                
        error = None
        if configlimits['sliceCountMax'] == 0:
            self.testlog.error("Unable to get slice count limit from %s",self.hostname)
            error = 1
        if configlimits['nodes_count'] == 0:
            self.testlog.error("Unable to get nodes count limit from %s",self.hostname)    
            error = 1
        if configlimits['memory_limit'] == 0:
            self.testlog.error("Unable to get memory limit from %s",self.hostname)    
            error = 1
        if configlimits['files_count'] == 0:
            self.testlog.error("Unable to get files count limit from %s",self.hostname)
            error = 1
        if error: 
            self.testlog.debug("returning -1")
        return configlimits
    
    
    def GetConfigValues(self):
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.ip)
        files = ['/anonymous/config/mdscore',
                 '/anonymous/config/mdscore-local',
                 '/anonymous/config/ssm',
                 '/anonymous/config/ssm-local'
                ]
        configvalues = {}
        command = "cat "
        for myfile in files:
            mycommand = command + myfile
            output,error = MGComm.sendsshcmd(self.ssh,mycommand)
            if error:
                if "No such file" in error: continue
                self.testlog.error(error)
                return -1
            for line in output:
                m = re.match("\s*\#",line)
                if m: continue
                line = line.strip()
                m = re.search("([\w\_\-]*)\s*\=*\s*(.*)",line)
                if m:
                    configvalues[m.groups()[0]] = m.groups()[1]
        return configvalues
                

         
    def GetHostName(self):
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.ip)
        output,error = MGComm.sendsshcmd(self.ssh,"hostname")
        if error:
            self.testinfo.error = "%s: Unable to get hostname for %s: %s" %\
                                     thisfunc,self.ip,error
            return -1
        hostname = output[0]
        msg = "hostname: " + hostname
        self.testlog.debug(msg)
        self.testlog.debug(thisfunc + ": returning " + hostname)
        return hostname
     
    def GetFileSystemName(self)

        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        command = "ls --color=none /anonymous/oufs"
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            self.testinfo.error = "%s unable to get file system name for %s: %s" %\
                thisfunc,self.hostname,error
            return -1
        filesystemname = output[0]
        filesystemname.strip()
        return filesystemname
         
             
     
    def GetSoftwareVersion(self):
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        output,error = MGComm.sendsshcmd(self.ssh,"rpm -qa|grep anonymous")
        if error:
            self.testinfo.error = "%s unable to get cld status for %s: %s" %\
                thisfunc,self.hostname,error
            return -1
         
        info = {}
        for item in output:
            part1,part2 = item.partition("-")[::2]
            info[part1] = part2
        return info
 
    def GetCLDStatus(self)
    '''
    Gets the cld status from the service command
    returns status or -1 on error
    If unable to get the status, as is often the case when the 
    cld is being booted up, an error is available to the 
    caller but is not logged'''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        output,error = MGComm.sendsshcmd(self.ssh,"service omcld status")
        if error:
            self.testinfo.error = "%s unable to get cld status for %s: %s" %\
                thisfunc,self.hostname,error
            return -1
        status = {}
        worst = None
        for item in output:
            parts = item.split()
            key = parts[0]
            stat = parts[-1]
            stat = re.sub('\.+',"",stat)
            status[key] = stat
            if worst == None:
                worst = stat
            else:
                if worst != stat:
                    if worst == "running":
                        worst = stat
                    elif worst == "stopped":
                        if stat == "dead": worst = stat
                     
            status['status'] = worst
        return status
       
    def GetDiscoveredDevices(self):
        '''The cld should contain a list of proprietary devices
           This method captures that list'''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        ssinfo = self.GetSliceServerInfo()  
        output,error = MGComm.sendsshcmd(self.ssh,"/opt/omutils/bin/discover")
        if error:
            self.testinfo.error = "%s unable to get discovered devices for %s %s" % (thisfunc, self.hostname, error)
            return -1
        devices = {}
        for item in output:
#             print "item:", item
            if item.find("Starting broadcast") != -1:
#                 print "item is Starting broadcast"
                continue
            if item.find("Timed out") != -1:
#                 print "item is Timed out"
                continue
#             print "processing:",item
            parts = item.split()
            ip = parts[0] 
            mgtype = parts[1]
            mgname = parts[2]
            mgname = re.sub("name=","",parts[2])
            mgtype = re.sub("type=","",parts[1])
            mgname = mgname.lower()
        
#             print "mgtype: %s mgname: %s  ip: %s" % (mgtype,mgname,ip)
#           We found a new device
            if mgname not in devices:
                devices[mgname] = {}
                devices[mgname]['hostname'] = mgname
                 
            m = re.search("BMC|CSJ|CSJHC|CSS|Controller",mgtype)
            if (m != None):
#                devices[mgname]['ip'] = {'public': [], 'private': []}
                if mgtype not in devices[mgname]:
                    if 'type' not in devices[mgname]:
                        devices[mgname]['type'] = "MGRAID-Controller"
                    devices[mgname][mgtype] = {}
                if 'ip' not in devices[mgname][mgtype]: 
                    devices[mgname][mgtype]['ip'] = []
                devices[mgname][mgtype]['ip'].append(ip)
                if "CSS" in mgtype and "model" not in devices[mgname] and ssinfo:
                    for item in ssinfo:
                        serialno = ssinfo[item]["serialno"]
                        serialno = serialno.lower()
                        serialno = serialno[0:-2]
                        if serialno in mgname:
                            devices[mgname]['model'] = ssinfo[item]['model']
                            self.testlog.debug("CSS %s model is %s" % (mgname,devices[mgname]['model']))
                                
            else:
                # listings for cld don't specify a type
                if mgtype == "USM-MDS":
                    m = re.match("10\.4",ip)
                    if m != None:
                        ipkey = "public"
                    else:
                        ipkey = "private"
                    if 'ip' not in devices[mgname]:
                        devices[mgname]['ip'] = {'public': [], 'private': []}
                    devices[mgname]['ip'][ipkey].append(ip)
                else:        
                    if 'ip' not in devices[mgname]: devices[mgname]['ip'] = []
                    devices[mgname]['ip'].append(ip)
                devices[mgname]['type'] = mgtype
 
#         print "devices:",devices
        return devices
    
      
    def parseVolumeOutput(self,output):
    ''' Parses the output from the GetVolInfo method'''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        volinfo = {}
        self.testlog.debug("PROCESSING OUTPUT:\n%s" % output)
        for line in output:
            line = line.strip()
            if "permission denied" in line:
                self.testlog.error("%s: ssmdiag -v command failed: %s" %\
                                   (self.hostname,line))
                return None
            line = line.replace("VID=0 ","")
            if 'group' in line:
#                 print thisfunc,"Processing",line
                fields = line.split(" ")
                if len(fields) < 4:
                    self.testlog.error("%s: parsing error for line: %s" \
                                       % (self.hostname,line))
#                 print thisfunc,"fields:",fields
                volinfo['vid'] = 0
                volinfo['groups'] = int(fields[0].replace("groups=",""))
                volinfo['sservers'] = fields[1].replace("servers=","")
                m = re.search("TB\=([\d\.]*)\/([\d\.]*)",fields[2])
                if m:
                    volinfo['usedspace'] = float(m.groups()[0])
                    volinfo['usedspace'] *= 1024**4
                    volinfo['totalspace'] = float(m.groups()[1])
                    volinfo['totalspace'] *= 1024**4
                    volinfo['slicecount'] = int(fields[3].replace("SC=",""))
            elif "CID" in line:
                line = line.replace("VID=0 CID=","")
                values = re.compile('\d+').findall(line)
                volinfo['cid'] = values.pop()
            elif "GID:" in line:
                line = line.replace("GID: ","")
                values = re.compile('\d+').findall(line)
                volinfo['groupids'] = values
                
                
                volinfo['groupids'] = values
        self.testlog.debug("returning: %s" % volinfo)
        return volinfo
                
                    
        
    
    def parseDetailedVolumeOutput(self,output):
        '''
        # Scope: PRIVATE
        # Status: Complete
        # Description: parse output from ssmdiag -v0 into a hash
        # Input Parameters:
        #  output - REQUIRED - output the the ssmdiag -v0 command
        # Output: volinfo hash
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        volinfo = {}
        volobject = None
        name = None
        for line in output:
            line = line.strip()
            if not line: continue
            m = re.match("(SSID|GID|VID)(?:\~|\=)(\d+)\s",line)
            if not m: continue
            t1 = m.groups()[0]
            t2 = m.groups()[1]
            name = t1 + t2
            if t1 == "SSID":
                if "sliceservers" not in volinfo:
                    volinfo['sliceservers'] = {}
                if name not in volinfo['sliceservers']:
                    volinfo['sliceservers'][name] = {}
                volobject = volinfo['sliceservers'][name]
            else:
                if name not in volinfo:
                    volinfo[name] = {}
                volobject = volinfo[name]
            line = re.sub("(SSID|GID|VID)(?:\~|\=)(\d+)\s+","",line)
            line = line.strip()
            
            m = re.search('bytes allocation\=(\d+)\/(\d+)',line)
            if m:
                volobject['space'] = {}
                volobject['space']['used']= m.groups()[0]
                volobject['space']['total']= m.groups()[1]
                continue
            m = re.search('groups=(\d+) servers=(\d+)',line)
            if m:
                volobject['groups']= m.groups()[0]
                volobject['servers']= m.groups()[1]
                continue
            m = re.search('slice images=(\d+)',line)
            if m:
                volobject['slices']= m.groups()[0]
                continue
            m = re.search('highest SID=(\w+) RF=(.*)',line)
            if m:
                volobject['highestsid']= m.groups()[0]
                volobject['repfactor']= m.groups()[1]
                continue
            m = re.search('GID: (.*)',line)
            if m:
                volobject['gid']= m.groups()[0]
                continue
            m = re.search('servers=(\d+)',line)
            if m:
                volobject['servers']= m.groups()[0]
                continue
            m = re.search('slices=(\d+)\/(\d+)',line)
            if m:
                volobject['slices'] = {}
                volobject['slices']['used']= m.groups()[0]
                volobject['slices']['max']= m.groups()[1]
                continue
            m = re.search('SSID: (.*)',line)
            if m:
                volobject['ssids']= m.groups()[0]
                continue
            m = re.search('SN=(\w+) MODEL=([\w\-]+) IP=(.*) PROTO=(\d+)',line)
            if m:
                volobject['sn']= m.groups()[0]
                volobject['model']= m.groups()[1]
                volobject['ips']= m.groups()[2]
                volobject['proto']= m.groups()[3]
                continue
            m = re.search('slices=(\d+) ready=(\d+)',line)
            if m:
                volobject['slices']= m.groups()[0]
                volobject['slicesready']= m.groups()[1]
                continue
            m = re.search('replicates queued=(\d+) pending=(\d+) launched=(\d+) done=(\d+) migrating=(\d+)',line)
            if m:
                volobject['replicates'] = {}
                volobject['replicates']['queued']= m.groups()[0]
                volobject['replicates']['pending']= m.groups()[1]
                volobject['replicates']['launched']= m.groups()[2]
                volobject['replicates']['done']= m.groups()[3]
                volobject['replicates']['migrating']= m.groups()[4]
                continue
            m = re.search('evacuation=(\w+) counter=(.*)',line)
            if m:
                volobject['evacuation']= m.groups()[0]
                volobject['evaccounter']= m.groups()[1]
                continue
            m = re.search('iobandwidth (\d+)',line)
            if m:
                volobject['iobandwidth']= m.groups()[0]
                continue
            m = re.search('slice ios=(\d+) errors=(\d+)',line)
            if m:
                volobject['sliceios']= m.groups()[0]
                volobject['sliceioserrors']= m.groups()[1]
                continue
            m = re.search('slices reads=(\d+) writes=(\d+) deletes=(\d+)',line)
            if m:
                volobject['slice'] = {}
                volobject['slice']['reads']= m.groups()[0]
                volobject['slice']['writes']= m.groups()[1]
                volobject['slice']['deletes']= m.groups()[2]
                continue
            m = re.search('error reads=(\d+) writes=(\d+) lost=(\d+)',line)
            if m:
                volobject['sliceerror'] = {}
                volobject['sliceerror']['reads']= m.groups()[0]
                volobject['sliceerror']['writes']= m.groups()[1]
                volobject['sliceerror']['lost']= m.groups()[2]
                continue
            m = re.search('rss=(\d+)\% total=(\d+) free=(\d+)',line)
            if m:
                volobject['rss'] = {}
                volobject['rss']['percent']= m.groups()[0]
                volobject['rss']['total']= m.groups()[1]
                volobject['rss']['free']= m.groups()[2]
                continue
            m = re.search('scache=(\d+)\% total=(\d+) free=(\d+)',line)
            if m:
                volobject['scache'] = {}
                volobject['scache']['percent']= m.groups()[0]
                volobject['scache']['total']= m.groups()[1]
                volobject['scache']['free']= m.groups()[2]
                continue
            m = re.search('ioq metric=(\d+) depth=(\d+) delay=(.*)',line)
            if m:
                volobject['ioq'] = {}
                volobject['ioq']['metric']= m.groups()[0]
                volobject['ioq']['depth']= m.groups()[1]
                volobject['ioq']['delay']= m.groups()[2]
                continue
            m = re.search('load averages=\( (.*) \)',line)
            if m:
                volobject['loadaverages']= m.groups()[0]
                continue
            m = re.search('sliced=(\w+).*stability=(\w+) access=(\w+) monitor=(.*)',line)
            if m:
                volobject['sliced']= m.groups()[0]
                volobject['stability']= m.groups()[1]
                volobject['access']= m.groups()[2]
                volobject['monitor']= m.groups()[3]
                continue
            m = re.search('discovered=(.*) probed=(.*) probes=(\d+)',line)
            if m:
                volobject['discovered']= m.groups()[0]
                volobject['probed']= m.groups()[1]
                volobject['probes']= m.groups()[2]
                continue
            m = re.search('IP=(\w+) speed=(\d+) RPCS=(.*) errors=(.*)',line)
            if m:
                ip = m.groups()[0]
                if 'ips' not in volobject: volobject['ips'] = {}
                volobject['ips'][ip] = {}
                volobject['ips'][ip]['speed']= m.groups()[1]
                volobject['ips'][ip]['RPCs']= m.groups()[2]
                volobject['ips'][ip]['errors']= m.groups()[3]
                continue
                
        self.testlog.debug("returning voinfo: %s" % str(volinfo))
        return volinfo
        

    
    def GetVolInfo(self,*args):  
        ''' get the volume information from command: ssmdiag -v 
        # Input: self - required
        #        detailed (arg[0]) - optional - if 1 the
        #        ssmdiag -v0 command is used to obtain more details
        #        default is 0
        # Output:
        #   on success - returns volinfo - a hash containing:
        #       volinfo['vid']   = volume id (normally 0)
        #       volinfo['groups']  = number of groups (normally 1)
        #       volinfo['sservers'] = number of servers
        #       volinfo['usedspace'] = used space in bytes
        #       volinfo['totalspace'] = total space in bytes
        #       volinfo['slicecount']  = slice count for the volume
        #       volinfo['cid'] = CID (normally 0)
        #       volinfo['groupids'] = array of group ids (normally there is only 1)
        #  if detailed the hash contains:
        #   volinfo['VIDn'] - where n is the volume number
        #   volinfo['VIDn']['space']['used'] = bytes of space used
        #   volinfo['VIDn']['space']['total'] = total bytes of space
        #   volinfo['VIDn']['groups'] = number of groups
        #   volinfo['VIDn']['servers'] = number of slice servers
        #   volinfo['VIDn']['slices'] = number of slice images
        #   volinfo['VIDn']['highestsid'] = Highest Slice ID
        #   volinfo['VIDn']['gid'] = group ID
        #   volinfo['GIDn'] - where n is the group number
        #   volinfo['GIDn']['servers'] = number of slice servers
        #   volinfo['GIDn']['space']['used'] = bytes of space used
        #   volinfo['GIDn']['space']['total'] = total bytes of space
        #   volinfo['GIDn']['slices']['used'] = number of slices used
        #   volinfo['GIDn']['slices']['total'] = maximum slices allowed
        #   volinfo['GIDn']['ssids'] = the slice ids in this group (space separated)
        #   volinfo['SSIDn'] - where n is the slice server number
        #   volinfo['SSIDn']['sn'] - controller serial number
        #   volinfo['SSIDn']['model'] - controller model number
        #   volinfo['SSIDn']['ips'] - slice server ips (space separated)
        #   volinfo['SSIDn']['proto'] - proto number
        #   volinfo['SSIDn']['space']['used'] = bytes of space used
        #   volinfo['SSIDn']['space']['total'] = total bytes of space
        #   volinfo['SSIDn']['slices'] - number of slices used
        #   volinfo['SSIDn']['slicesready'] - percentage ready (no percent sign)
        #   volinfo['SSIDn']['replicates']['queued'] - number of replicates queued
        #   volinfo['SSIDn']['replicates']['launched'] - number of replicates launched
        #   volinfo['SSIDn']['replicates']['done'] - number of replicates done
        #   volinfo['SSIDn']['replicates']['migrating'] - number of replicates migrating
        #   volinfo['SSIDn']['evacuation'] - evacuation status
        #   volinfo['SSIDn']['evaccounter'] - evacuation counter (n/n)
        #   volinfo['SSIDn']['iobandwidth'] - io bandwidth in MB/s
        #   volinfo['SSIDn']['sliceios'] - slice io counter
        #   volinfo['SSIDn']['sliceioserrors'] - slice io error counter
        #   volinfo['SSIDn']['sliceioserrors'] - slice io error counter
        #   volinfo['SSIDn']['slice']['reads'] - slice read counter
        #   volinfo['SSIDn']['slice']['writes'] - slice write counter
        #   volinfo['SSIDn']['slice']['deletes'] - slice delete counter
        #   volinfo['SSIDn']['sliceerror']['reads'] - slice read error counter
        #   volinfo['SSIDn']['sliceerror']['writes'] - slice write error counter
        #   volinfo['SSIDn']['sliceerror']['lost'] - slice lost counter
        #   volinfo['SSIDn']['rss']['percent'] - percent of rss used
        #   volinfo['SSIDn']['rss']['total'] - total rss
        #   volinfo['SSIDn']['rss']['free'] - free rss
        #   volinfo['SSIDn']['scache']['percent'] - percent of scache used
        #   volinfo['SSIDn']['scache']['total'] - total scache
        #   volinfo['SSIDn']['scache']['free'] - free scache
        #   volinfo['SSIDn']['ioq']['metric'] - ioq metric
        #   volinfo['SSIDn']['ioq']['depth'] - ioq depth
        #   volinfo['SSIDn']['ioq']['delay'] - ioq delay (i.e. 0ms)
        #   volinfo['SSIDn']['ioq']['loadaverages'] - load averages (space separated)
        #   volinfo['SSIDn']['sliced'] - TDB current value is "OK"
        #   volinfo['SSIDn']['stability'] - TDB current value is "OK"
        #   volinfo['SSIDn']['access'] - TDB current value is "ONLINE"
        #   volinfo['SSIDn']['monitor'] - TDB current value is "RECONCILE (7)"
        #   volinfo['SSIDn']['discovered'] - TDB current value is "<>"
        #   volinfo['SSIDn']['probed'] - TDB value example: 150929:17:21:26.402
        #   volinfo['SSIDn']['probes'] - number of probes example: 150929:17:21:26.402
        #   volinfo['SSIDn']['ip']['<ipaddr>']['speed'] - link speed
        #   volinfo['SSIDn']['ip']['<ipaddr>']['rpcs'] - rps over link i.e. 644619:12
        #   volinfo['SSIDn']['ip']['<ipaddr>']['errors'] - errorsover link i.e. 0:0
        #
        #   on failure - logs error and returns None
        '''
        detailed = 0
        if len(args): detailed = args[0]
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        command = "/opt/omcld/bin/ssmdiag -v"
        if detailed: command = command + "0"
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            return None
        volinfo = None
        if not detailed:
            volinfo = self.parseVolumeOutput(output)
        else:
            volinfo = self.parseDetailedVolumeOutput(output)
        self.testlog.debug("returning voinfo: %s" % str(volinfo))
        return volinfo

    
    def GetEvacuationInfo(self,ssid):
        ''' issues the command /opt/omcld/bin/ssmdiag -sE<ssid> command and
        parses the output to obtain the evacuation information.  Returns a
        dictionary with the following elements:
            evacinfo['status'] - string i.e. "IDLE"
            evacinfo['volspace'] - integer space in GB
            evacinfo['groupspace'] - integer space in GB
            if evac is running:
            evacinfo['counter']['slicesdone'] - number of slices replicated
            evacinfo['counter']['totalslices'] - total number of slices to be replicated
            evacinfo['percentcomplete'] - percent of evac completed
            evacinfo['slicespersec'] - slices replicated per second
            evacinfo['datetime'] - the date and time the operation is expected to complete
            if evacuation has been run there will be additional information:
            evacinfo['Stage']['avg'] - average ???
            evacinfo['Stage']['min'] - minimum ???
            evacinfo['Stage']['max'] - maximum ???
            evacinfo['Submit']['avg'] - average ???
            evacinfo['Submit']['min'] - minimum ???
            evacinfo['Submit']['max'] - maximum ???
            evacinfo['Launch']['avg'] - average ???
            evacinfo['Launch']['min'] - minimum ???
            evacinfo['Launch']['max'] - maximum ???
            evacinfo['Launch']['missed'] - missed ???
            evacinfo['Complete']['avg'] - average ???
            evacinfo['Complete']['min'] - minimum ???
            evacinfo['Complete']['max'] - maximum ???
           
        Returns evacinfo or None if an error or no info was returned
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        command = '/opt/omcld/bin/ssmdiag -sE' + ssid
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            return None
        if not output:  return None
        evacinfo = {}
        for line in output:
            if "Post" in line:
                params = re.findall("\d+",line)
                if len(params) != 3:
                    self.testlog.error(\
                      "did not find evac space info in line:\n%s" % line)
                    return None
                evacinfo['volspace'] = params[1]
                evacinfo['groupspace'] = params[2]
                continue
            if "evacuation=" in line:
                m = re.search("evacuation=(\w+)",line)
                if not m:
                    self.testlog.error(\
                    "did not find evac status and counter in line" % line)
                    continue
                params = m.groups()
                evacinfo['status'] = params[0]
                if params[0] == "IDLE": continue
                m = re.search(
                    "counter=(\d+)\/(\d+)\s([\d\%]+)\s([\d\.]+)\sslices\/sec\s(.*)",
                              line)
                if not m:
                    self.testlog.warning("unable to get params from line:\n%s",
                                         line)
                    continue
                params = m.groups()
                evacinfo['counter'] = {}
                evacinfo['counter']['slicesdone'] = params[0]
                evacinfo['counter']['totalslices'] = params[1]
                evacinfo['percentcomplete'] = params[2]
                evacinfo['slicespersec'] = params[3]
                evacinfo['datetime'] = params[4]
                continue
            m = re.search("(Stage|Submit|Launch|Complete):",line)
            if m:
                thekey = m.groups()[0]
                evacinfo[thekey] = {}
                stuff = re.findall('(\w+)\=\s*([\d.]+)\s*',line)
                for item in stuff:
                    if item[0] == "SSID": continue
                    evacinfo[thekey][item[0]] = item[1]
                continue
        return evacinfo
    
    def GetBalancerInfo(self):
        ''' parses the output from /opt/omcld/bin/ssmdiag -bs' into
            a dictionary.
            Right now we skip the schedule information, may want to revisit
            that later.
            output:
                binfo['slicebalanced'] - number of slices to be balanced
                binfo['slicetobebalanced'] - number of slices to be balanaced
                binfo['suspended'] - 0 if balancer not suspended, 1 if it is
                binfo['running'] - 1 if balancer is running, 0 if it is not
                binfo['hosting'] - is 1 is the cld is hosting the balancer, 0 if not
                binfo['hint'] - nn ???
                binfo['status'] - active or diabled
            returns binfo unless unable to get the information, then it 
            returns None
        '''
        command = '/opt/omcld/bin/ssmdiag -bs'
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            return None
        binfo = {}
        for line in output:
            if "day" in line: continue
            line = line.strip()
            parts = line.split(" = ")
            key = parts[0].replace  (" ","")
            binfo[key] = int(parts[1])
        # get status of the balancer (active for disabled)
        command = '/opt/omcld/bin/ssmdiag -b'
        output,error = MGComm.sendsshcmd(self.ssh, command)
        binfo['status'] = None
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
        else:
            if "active" in output[0]: 
                binfo['status'] = "active"
            elif "disabled" in output[0]:
                binfo['status'] = "disabled"
            
        return binfo

    def StartRogueHunter(self,*args):
        ''' uses the ssmdiag -V command to start the rogue hunter
        if a SSID is included in the args, the rogue hunter will be 
        started on that slice server
        On error:  reports the error and returns -1 
        returns None
        TODO: should check to see if it is running
        '''
        ssid = None
        if args:
            ssid = args[0]
        command = '/opt/omcld/bin/ssmdiag -V'
        if ssid != None: command = command + ssid
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            return -1
        return None
    
    def StartSliceStabilizer(self,*args):
        ''' uses the ssmdiag -T4 command, 
            This wakes up the ssmSliceStabilizer() thread which runs (in this order):
        Input: OPTIONAL ARGS:
               arg[0] - is wait flag 0 - no wait  1 - wait
               arg[1] - wait timeout value in seconds - default wait timeout is 600
        On error:  reports the error and returns -1 
        returns -1 if an error occurred
                 1 if the stabilizer completed
                 None if the stabilizer did not complete, or we did not wait for it to complete
        '''
        monq = None
        wait = None
        timeout = 600
        if args:
            wait = args[0]
            if len(args) > 1:
                timeout = int(args[1])
        self.testlog.debug("timeout = %d" % timeout)
                
        command = '/opt/omcld/bin/ssmdiag -T4'
        complete = None
        if wait:
            self.monitors['ssmd'].trace = 1
            monq = self.monitors['ssmd'].addwriteq()
            self.monitors['ssmd'].ReportlistAdd("ssmSliceStabilizer")
            self.testlog.debug("ssmd monitor type: %s" % self.monitors['ssmd'].__dict__)
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            complete = -1
        if wait and not complete:
            starttime = time.time()
            while (time.time() - starttime) < timeout:
                if monq.empty():
                    sleep(1)
                    continue
                logmsg = monq.get_nowait()
                self.testlog.debug("got message: %s" % logmsg)
                if "ssmSliceStabilizer" in logmsg and "done" in logmsg:
                    complete = 1 
                    break
        if wait:
            self.monitors['ssmd'].removewriteq(monq)
            self.monitors['ssmd'].ReportlistRemove("ssmSliceStabilizer")
        self.monitors['ssmd'].trace = 1    
        return complete
    
   
    def StartStopSSBalancer(self,cmd):
        '''Start or stop the enabled balancer
        cmd: start - start the balancer operation
             stop - stop the running balancer
        return 0 on success, -1 on failure
        errors are logged to the testlog'''
        thisfunc = inspect.stack()[0][3]
        cmd = cmd.lower()
        if cmd != "stop" and cmd != "start":
            self.testlog.error('cmd parameter must be "stop" or "start"')
            return -1
        command = '/opt/omcld/bin/ssmdiag -bs' + cmd
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            return -1
        command = '/opt/omcld/bin/ssmdiag -bs'
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            return -1
        rc = 0
        for line in output:
            if "running = 0" in line:
                if cmd == "start":
                    print thisfunc,"line:",line 
                    self.testlog.error("balancer not started")
                    rc = -1
                break
            if "running = 1" in line:
                print thisfunc,"line:",line 
                if cmd == "stop": 
                    self.testlog.error("balancer not stopped")
                    rc = -1
                break
        return rc
    
    def EnableDisableBalancer(self,cmd)
    '''Issues command to enable/disable the balancing of slices cross 
       clds.  
       cmd = 0 or 1: 0 - disable  1 = enable
       returns 0 - success  -1 - error
       all errors are logged in the testlog
    '''
        cmd = str(cmd)
        if cmd != "0" and cmd != "1":
            self.testlog.error("cmd parameter must be '0' or '1'")
            return -1
        command = "/opt/omcld/bin/ssmdiag -b" + cmd
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            return -1
        command = "/opt/omcld/bin/ssmdiag -b"
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            return -1
        setting = None
        rc = 0
        for line in output:
            if "active" in line:
                if cmd == "0": self.testlog.error("balancer not disabled") 
                setting = '1'
                rc = -1
                break
            if "disabled" in line:
                if cmd == "0": self.testlog.error("balancer not enabled")
                rc = -1 
                break
        return rc        
        
        
                
                
    def SetShelfMode(self,**kwargs):
        '''
            Set a shelf (a set of hard drives) to read-delete or read-write
            (normal mode) via ssmdiag
            uses ssmdiag -s<ssid> to verify the shelf is set to the correct
            mode.
            Input:
                mode=<r|w> - Optional - default is read-write
                ssid=<shelf ssid> - Required - the ssid of the shelf.
                answer=<y|n> - Optional - verification answer default "y"
            Output:
                success = None
                failure = -1
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        if "ssid" not in kwargs.keys():
            self.testlog.error("ssid keyword argument is required")
            return -1
        if 'answer' not in kwargs.keys():
            answer = "y\n"
        else:
            answer = kwargs['answer'].upper() + "\n"
        shid = kwargs['ssid']
        if "mode" not in kwargs.keys():
            mode = 'w'
        else:
            mode = kwargs['mode'].lower()
        if mode != "r" and mode != "w":
            self.testlog.error("mode value must be 'r' or 'w': mode = %s" % mode)
            return -1
        if mode == "r":
            self.testlog.info("shelf %s setting mode to READ-DELETE" % shid)
        else:
            self.testlog.info("shelf %s setting mode to read write" % shid)
        command = "/opt/omcld/bin/ssmdiag -D" + mode + str(shid)
        
        output = self.SendVerifiedCommand(command,answer)
        sleep(10)
        
        shelfinfo = self.GetSliceServerInfo(ssid=shid)
        if not shelfinfo:
            self.testlog.debug("returning -1")
            return -1
        rc = None
        if mode == "w" and shelfinfo[shid]['sliced'] != "OK":
            msg = "shelf %s sliced value is %s expected OK" \
                % (shelfinfo[shid]['serialno'],shelfinfo[shid]['sliced'])
            self.testlog.error(msg)
            rc = -1
        elif mode == "r" and shelfinfo[shid]['sliced'] != "READ-DELETE":
            msg = "shelf %s sliced value is %s expected READ-DELETE" \
                % (shelfinfo[shid]['serialno'],shelfinfo[shid]['sliced'])
            self.testlog.error(msg)
            rc = -1
        self.testlog.debug("returning %s" % rc)
        return rc
            
        
    def EvacuateShelf(self,**kwargs):
        ''' used ssmdiag to evacuate a shelf
            Input:  takes the following keyword arguments
                ssid=<ssid for the shelf> - Required - 
                     the sliceserver id for the shelf
                answer=<y|n> - Optional - answer for verification prompt
                    default is "y"
            Output:
                if error: -1
                if success: None
        '''
        self.testlog.debug("%s: starting",self.hostname)
        if 'ssid' not in kwargs.keys():
            self.testlog.error("ssid is a required parameter")
            return -1
        shid = kwargs['ssid']
        if 'answer' not in kwargs.keys():
            answer = "y\n"
        else:
            answer = kwargs['answer'].upper() + "\n"
            
        command = "/opt/omcld/bin/ssmdiag -D" + str(shid)
        output = self.SendVerifiedCommand(command,answer)
        sleep(5)
        shelfinfo = self.GetEvacuationInfo(shid)
        if shelfinfo['status'] != "ACTIVE":
            self.testlog.error("%s: evacuation status is %s should be ACTIVE" \
                               % (shid,shelfinfo['status']))
            return -1
        return None
    
    def SetEvacuationPriority(self,priority):
        ''' set and get the Evacuation priority.  
            the priority value should be: 'high', 'normal', or None
            if None this just returns the current priority
            This function verifies the priority
            an error is logged if the priority is not set correctly
            output: None if error
                    if no error returns the current priority ("high" or "normal")
        '''
        self.testlog.debug("priority parameter is %s" % priority)
        if priority != None:
            priority = priority.lower()
            if priority != "normal" and priority != "high":
                self.testlog.error("'priority' parameter must be 'normal', 'high' or None")
                return None
            command = "/opt/omcld/bin/ssmdiag -Dp" + priority
            output,error = MGComm.sendsshcmd(self.ssh, command)
            if error:
                msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
                  % (self.hostname,command,error)
                self.testlog.error(msg)
                return None
        command = "/opt/omcld/bin/ssmdiag -Dp" 
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            return None
        currentpriority = None
        if "High" in output[0]:
            currentpriority = "high"
        elif "Normal" in output[0]:
            currentpriority = "normal"
        else:
            currentpriority = None
        if priority and priority != currentpriority:
            self.testlog.error(
                "Attempt to set evacuation priority to %s failed, current priority: %s"
                 % (priority,currentpriority))
        elif priority:
            self.testlog.info("Evacuation priority is set to %s" % currentpriority)
        return currentpriority
            
            
            
            
    
    def CancelShelfEvacuation(self,ssid):  
        ''' Uses ssmdiag to Cancel the evacuation of a shelf that is 
        actively evacuating.
        Input:
            ssid - required - the ssid of the shelf
        Output:
            None on success
            1  if shelf is not actively evacuating
            -1 on Error
        '''
        shinfo = self.GetEvacuationInfo(ssid)
        if shinfo['status'] != "ACTIVE":
            return 1
        command = "/opt/omcld/bin/ssmdiag -Dq" + str(ssid)
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            return None
        sleep(5)
        shinfo = self.GetEvacuationInfo(ssid)
        if shinfo['status'] != "IDLE":
            self.testlog.error(
                "%s: expected evacuation status IDLE  actual %s" \
                % (ssid,shinfo['status']))
            return -1
        return None
        
        
                
        
    def SendVerifiedCommand(self,command,answer):
        ''' send a command where there is a verification step of "Are you sure"
        '''
        transport = self.ssh.get_transport()
        transport.set_keepalive(1)
        channel = transport.open_session()
        channel.settimeout(5)
#        cfile = channel.makefile()
        print "sending command %s" % command
        channel.exec_command(command)
        output = []
        while not channel.exit_status_ready():
            try:
                line = channel.recv(1025)
#                 line = cfile.read(1024)
#                 line = line.rstrip()
            except Exception, e:
                continue
            if "Are you sure" in line:
                channel.send(answer)
#                 cfile.write(answer)
                continue
            elif line:
                print "line:",line
                output.append(line)
        channel.close()
        return output
    
                
    def GetSliceServerInfo(self,**kwargs):
        '''Uses ssmdiag -s to gather slice server information'''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        if "detailed" in kwargs.keys():
            detailed = kwargs['detailed']
        else:
            detailed = None
        if 'ssid' in kwargs.keys():
            ssid = kwargs['ssid']
        else:
            ssid = None
        
        command = "/opt/omcld/bin/ssmdiag -s"
        if detailed: 
            command = command + "-1"
        elif ssid:
            command = command + ssid
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            msg = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            self.testlog.error(msg)
            return None
        ssinfo = None
        if ssid:
            ssinfo = self.parseDetailedSliceServerOutput(output)
        elif detailed:
            ssinfo = self.parseDetailedSliceServerOutput(output)
        else:
            ssinfo = self.parseSliceServerOutput(output)
        self.testlog.debug("returning ssinfo: %s" % str(ssinfo))
        return ssinfo
        
    def parseSliceServerOutput(self,output):
        '''parse summary output'''
        ssinfo = {}
        mysearch = re.compile(\
            "(.)SSID[=~](\d+)\s+/(\d+) SN=([\w\.]+)\s([\w\-]+)\s(.*) GB=(\d+)/(\d+) SC=(\d+)")
        for line in output:
            m = re.match(mysearch,line)
            if not m:
                self.testlog.warning(\
                   "oops: didn't get the ssid + params from:\n%s" % line)
                continue
            params = m.groups()
            ssinfo[params[1]] = {}
            ssinfo[params[1]]['ssids'] = [params[1],params[2]] # mdsclient uses both
            ssinfo[params[1]]['id'] = params[2]
            ssinfo[params[1]]['serialno'] = params[3]
            ssinfo[params[1]]['model'] = params[4]
            ssinfo[params[1]]['GB'] = {} 
            ssinfo[params[1]]['GB']['used'] = int(params[6])
            ssinfo[params[1]]['GB']['total'] = int(params[7])
            ssinfo[params[1]]['slicecount'] = params[8]
            ssinfo[params[1]]['status'] = params[0]
            ssinfo[params[1]]['ip'] = []
            ips = params[5].split(" ")
            for ip in ips:
                if ip != '':  ssinfo[params[1]]['ip'].append(ip)
        return ssinfo
        
        
    def parseDetailedSliceServerOutput(self,output):  
        '''parses the output from the ssmdiag -s<SSID> or ssmdiag -s-1 command 
        which consists of detailed output for the ssids or all the ssids as 
        specified.
        input:  the output of the ssmdiag -s-1 or -s<ssid> command
        output:  Dictionary
            
            ssinfo[<ssid>]['serialno'] - the serial number of the shelf (string)
            ssinfo[<ssid>]['model'] - the model number of the physical shelf (string)
            ssinfo[<ssid>]['proto'] - Not sure what this is (string)
            ssinfo[<ssid>]['ip'][<ipaddr>]['speed'] - speed in mbps (string)
            ssinfo[<ssid>]['ip'][<ipaddr>]['RPCs'] - nnnnn:n (string)
            ssinfo[<ssid>]['ip'][<ipaddr>]['errors'] - n:n (string)
            ssinfo[<ssid>]['bytealloc']['used'] - used bytes (integer)
            ssinfo[<ssid>]['bytealloc']['total'] - total bytes (integer)
            ssinfo[<ssid>]['bytealloc']['usedGB'] - used bytes in GB (integer)
            ssinfo[<ssid>]['bytealloc']['totalGB'] - total bytes in GB (integer)
            ssinfo[<ssid>]['slices'] - number of slices (integer)
            ssinfo[<ssid>]['slicesready'] - percent of slices ready  (string)
            ssinfo[<ssid>]['replicates']['queued'] - replicate slices queued (integer)
            ssinfo[<ssid>]['replicates']['launched'] - replicate slices launched (integer)
            ssinfo[<ssid>]['replicates']['pending'] - replicate slices pending (integer)
            ssinfo[<ssid>]['replicates']['done'] - replicate slices done (integer)
            ssinfo[<ssid>]['replicates']['migrating'] - replicate slices migrating (integer)
            ssinfo[<ssid>]['iobandwidth'] - io bandwidth in Mb/s  (integer)
            ssinfo[<ssid>]['slice']['ios'] - slice I/Os (integer)
            ssinfo[<ssid>]['slice']['errors'] - count of error in slice I/Os (integer)
            ssinfo[<ssid>]['slice']['reads'] - slice reads count (integer)
            ssinfo[<ssid>]['slice']['writes'] - slice writes count (integer)
            ssinfo[<ssid>]['slice']['deletes'] - lost slices count (integer)
            ssinfo[<ssid>]['errors']['reads'] - read errors count (integer)
            ssinfo[<ssid>]['errors']['writes'] - write errors count (integer)
            ssinfo[<ssid>]['errors']['lost'] - lost errors count (integer)
            ssinfo[<ssid>]['rss']['percent'] - rss percentage (string)
            ssinfo[<ssid>]['rss']['total'] - rss total (integer)
            ssinfo[<ssid>]['rss']['free'] - rss free (integer)
            ssinfo[<ssid>]['scache']['percent'] - scache percentage (integer)
            ssinfo[<ssid>]['scache']['total'] - scache total (integer)
            ssinfo[<ssid>]['scache']['free'] - scache free (integer)
            ssinfo[<ssid>]['ioq']['metric'] - ioq metric (integer)
            ssinfo[<ssid>]['ioq']['depth'] - ioq depth (integer)
            ssinfo[<ssid>]['ioq']['delay'] - ioq delay (integer)
            ssinfo[<ssid>]['loadaverages'] - array of 3 load averages containing integer values
            ssinfo[<ssid>]['sliced'] - sliced status (OK, READ-DELETE, EVACUATING) (string)
            ssinfo[<ssid>]['stability'] - OK or ??? (string)
            ssinfo[<ssid>]['access'] - ONLINE or ??? (string)
            ssinfo[<ssid>]['monitor'] - RECONCILE or ??? (string)
            ssinfo[<ssid>]['discovered'] - nnnnnn:nn:nn:nn.nnn ???  (string)
            ssinfo[<ssid>]['probed'] - nnnnnn:nn:nn:nn.nnn ???  (string)
            ssinfo[<ssid>]['probes'] - nnnn probe count ???  (string)
            ssinfo[<ssid>]['evacuation']['status'] - evacuation status (string)
            ssinfo[<ssid>]['evacuation']['counter']['slicesdone'] - number of slices evacuated (integer)
            ssinfo[<ssid>]['evacuation']['counter']['totalslices'] - total number of slices to evacuate (integer)
         if shelf evacuation is running:
            ssinfo['evacuation']['percentcomplete'] = percent of evacuation complete (string)
            ssinfo['evacuation']['slicespersec'] = slices evacuated per second (integer)
            ssinfo['evacuation']['datetime'] = date time ??? (string)
         if evacuation has been run there will be additional information:
            ssinfo[<ssid>]['Stage']['avg'] - average ??? (float)
            ssinfo[<ssid>]['Stage']['min'] - minimum ??? (float)
            ssinfo[<ssid>]['Stage']['max'] - maximum ??? (float)
            ssinfo[<ssid>]['Submit']['avg'] - average ??? (float)
            ssinfo[<ssid>]['Submit']['min'] - minimum ??? (float)
            ssinfo[<ssid>]['Submit']['max'] - maximum ??? (float)
            ssinfo[<ssid>]['Launch']['avg'] - average ??? (float)
            ssinfo[<ssid>]['Launch']['min'] - minimum ??? (float)
            ssinfo[<ssid>]['Launch']['max'] - maximum ??? (float)
            ssinfo[<ssid>]['Launch']['missed'] - missed ??? (float)
            ssinfo[<ssid>]['Complete']['avg'] - average ??? (float)
            ssinfo[<ssid>]['Complete']['min'] - minimum ??? (float)
            ssinfo[<ssid>]['Complete']['max'] - maximum ??? (float)
        
        if there is a problem parsing any of the lines a warning is logged, and the 
        lines continue to be processed     
        
        '''
        allssinfo = {}
        ssinfo = {}
        ssid = None        
        
        s1 = re.compile("\sSSID[\=\~](\d+)\s+(.*)")
        for line in output:
            line = line.rstrip()
#             print "processing line:",line
            m = re.match(s1,line)
            if not m:
                self.testlog.warning(\
                "oops: didn't get the parameters from line:\n%s" % line)
                continue
            (id,parameters) = m.groups()
            if not ssid:
                ssid = id
                ssinfo = {}
            elif ssid != id:
                allssinfo[ssid] = ssinfo
                ssid = id
                ssinfo = {}
            if "SN=" in parameters:
                m = re.match("SN=(.*)\sMODEL=(.*)\sIP=(.*)PROTO=(\d+)",parameters)
                if not m:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                params = m.groups()
                ssinfo['serialno'] = params[0]
                ssinfo['model'] = params[1]
                ssinfo['proto'] = int(params[3])
                ipaddrs = params[2].split(" ")
                ssinfo['ip'] = {}
                for ipaddr in ipaddrs:
                    if ipaddr != ' ' and ipaddr != '':
                        ssinfo['ip'][ipaddr] = {}
                continue
            if "byte allocation" in line:
                ssinfo['bytealloc'] = {}
                params = re.findall("\d+",parameters)
                if not params:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                ssinfo['bytealloc']['used'] = int(params[0])
                ssinfo['bytealloc']['total'] = int(params[1])
                ssinfo['bytealloc']['GBused'] = int(params[2])
                ssinfo['bytealloc']['GBtotal'] = int(params[3])
                continue
            if "slices=" in parameters:
                #slices=3885808 ready=100%
                m = re.match("slices=(\d+)\sready=([\d\%]+)",parameters)
                if not m:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                (ssinfo['slices'],ssinfo['slicesready']) = m.groups()
                ssinfo['slices'] = int(ssinfo['slices'])
                continue
            if "replicates" in parameters:
                params = re.findall("\d+",parameters)
                if not params:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                ssinfo['replicates'] = {}
                ssinfo['replicates']['queued'] = int(params[0])
                ssinfo['replicates']['pending'] = int(params[1])
                ssinfo['replicates']['launched'] = int(params[2])
                ssinfo['replicates']['done'] = int(params[3])
                ssinfo['replicates']['migrating'] = int(params[4])
                continue
            if 'evacuation' in parameters:
                params = re.findall("=([\w\/]+)",parameters)
                if not params:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                ssinfo['evacuation'] = {}
                ssinfo['evacuation']['status'] = params[0]
                if params[0] == "IDLE": continue
                ssinfo['evacuation']['counter'] = {}
                parts = params[1].split("/")
                ssinfo['evacuation']['counter']['slicesdone'] = int(parts[0])
                ssinfo['evacuation']['counter']['totalslices'] = int(parts[1])
                m = re.search("([\d\%]+)\s([\d\.]+)\sslices\/sec\s(.*)",parameters)
                if not m:
                    self.testlog.warning("unable to get params from line:\n%s",
                                         line)
                    continue
                params = m.groups()
                ssinfo['evacuation']['percentcomplete'] = params[0]
                ssinfo['evacuation']['slicespersec'] = params[1]
                ssinfo['evacuation']['datetime'] = params[2]
                continue
            if 'ioBandwidth' in parameters:
                m = re.search("(\d+)",parameters)
                
                ssinfo['iobandwidth'] = m.groups()[0]
                ssinfo['iobandwidth'] = int(ssinfo['iobandwidth'])
                continue
            if "slice " in parameters:
                if 'slice' not in ssinfo: ssinfo['slice'] = {}
                m = re.findall("(\w+=\d+)",line)
                for item in m:
                    (key,value) = item.split("=")
                    ssinfo['slice'][key] = int(value)
                continue
            if "error " in parameters:
                ssinfo['error'] = {}
                m = re.findall("(\w+=\d+)",line)
                for item in m:
                    (key,value) = item.split("=")
                    ssinfo['error'][key] = int(value)
                continue
            if "rss=" in parameters or 'scache' in parameters:
                if 'scache' in parameters:
                    key = 'scache'
                else:
                    key = 'rss'
                params = re.findall("=(\d+)",parameters)
                if not params:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                ssinfo[key] = {}
                ssinfo[key]['percent'] = params[0]
                ssinfo[key]['total'] = int(params[1])
                ssinfo[key]['free'] = int(params[2])
                    
            if "sliced" in parameters or "probed" in parameters:
                m = re.findall("(\w+=[\d\w:<>-]+)",line)
                if not m:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                for item in m:
                    (key,value) = item.split("=")
                    ssinfo[key] = value
                continue
            if "ioq " in parameters:
                ssinfo['ioq'] = {}
                m = re.findall("(\w+=\d+)",line)
                if not m:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                for item in m:
                    (key,value) = item.split("=")
                    ssinfo['ioq'][key] = int(value)
                continue
            if "load averages" in parameters:
                params = re.findall("\d+",parameters)
                ssinfo['loadaverages'] = params
                continue
            if "speed" in parameters:
                stuff = {}
                m = re.findall("(\w+=[\d\.\:]+)",line)
                if not m:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                for item in m:
                    (key,value) = item.split("=")
                    stuff[key] = value
                ssinfo['ip'][stuff['IP']].update(stuff)
                continue
            m = re.search("(Stage|Submit|Launch|Complete):",line)
            if m:
                thekey = m.groups()[0]
                ssinfo[thekey] = {}
                stuff = re.findall('(\w+)\=\s*([\d.]+)\s*',line)
                for item in stuff:
                    if item[0] == "SSID": continue
                    ssinfo[thekey][item[0]] = float(item[1])
#         print "ssinfo for",ssid,":\n",ssinfo
        if len(ssinfo):
            allssinfo[ssid] = ssinfo    
        return allssinfo        
    
    def GetSSGroupInfo(self,gid):
        ''' get the group information using ssmdiag -g.  If the gid 
        is not None, then it is appended to the command in order to
        obtain detailed information on a specific group or all groups
        if the gid is -1.
        if the gid is None, then the basic group information is returned
        for all groups. '''
        self.testlog.debug("%s: starting",self.hostname)
        command = "/opt/omcld/bin/ssmdiag -g"
        if gid: 
            command = command + gid
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            self.testinfo.error = "Failed to send command to %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,error)
            return None
        if not output:
            return None
        if "ssmNoEntryFound" in output[0]:
            self.testinfo.error = "Command failed on %s:\nCommand: %s\nError: %s" \
              % (self.hostname,command,output[0].strip())
            return None
            
        groupinfo = None
        if gid:
            groupinfo = self.parseDetailedGroupOutput(output)
        else:
            groupinfo = self.parseGroupOutput(output)
        self.testlog.debug("returning groupinfo: %s" % str(groupinfo))
        return groupinfo

    def parseGroupOutput(self,output):
        '''parse summary output for filesystem groups. Info is returned in a
        dictionary containing:
        groupinfo[groupid]['id'] - the group id (integer)
        groupinfo[groupid]['servercount'] - the number of slice servers in the group (integer)
        groupinfo[groupid]['TB'] - dictionary containing the space in group in TB
        groupinfo[groupid]['TB']['used'] - the amount of space used in TB (float)
        groupinfo[groupid]['TB']['total'] - the total amount of TB in group (float)
        groupinfo[groupid]['slicecount'] - the number of slices used in the group (integer)
        groupinfo[groupid]['status'] - the status of the group (online or offline)(integer)
        groupinfo[groupid]['servers'] - a list of the slice server ids in this group (chars)
        
        Note there is a groupinfo[groupid] dictionary for each group if there are multiple groups.
        i.e.  groupinfo[0]  groupinfo[1] ...
        
        If there are lines that do not match our regex search a warning is logged.  
        
        '''
        groupinfo = {}
        mysearch = re.compile("(.)GID=(.)\sservers=(.)\sTB=(.*)\/(.*)\sSC=(\d*)\sSSID:\s(.*)")
        for line in output:
            line = line.rstrip()
            m = mysearch.match(line)
            if not m:
                self.testlog.warning(\
                   "oops: didn't get line that was expected from ssmdiag -g on %s:\n%s" % 
                   (self.hostname,line))
                continue
            params = m.groups()
            self.testlog.debug("parseGroupOutput: params: %s" % str(params))
            groupinfo[params[1]] = {}
            groupinfo[params[1]]['id'] = int(params[1])
            groupinfo[params[1]]['servercount'] = int(params[2])
            groupinfo[params[1]]['TB'] = {} 
            groupinfo[params[1]]['TB']['used'] = float(params[3])
            groupinfo[params[1]]['TB']['total'] = float(params[4])
            groupinfo[params[1]]['slicecount'] = int(params[5])
            if params[0] == " ":
                status = "online"
            else:
                status = "offline"
            groupinfo[params[1]]['status'] = status
            groupinfo[params[1]]['servers'] = []
            sss = params[6].split(" ")
            for ss in sss:
                if ss != '' and ss != "<>":  groupinfo[params[1]]['servers'].append(ss)
            
        return groupinfo
        
        
    def parseDetailedGroupOutput(self,output):  
        '''parses the output from the ssmdiag -s<SSID> or ssmdiag -s-1 command 
        which consists of detailed output for the ssids or all the ssids as 
        specified.
        input:  the output of the ssmdiag -s-1 or -s<ssid> command
        output:  Dictionary
            groupinfo[<groupid>]['servercount'] - count of slice servers in group (integer)
            groupinfo[<groupid>]['byteallocation'] - dictionary containing the number of bytes used and total in group
            groupinfo[<groupid>]['byteallocation']['used'] - the number of bytes used (integer)
            groupinfo[<groupid>]['byteallocation']['total'] - the total number of bytes in group (integer)
            groupinfo[<groupid>]['slices'] - dictionary containing slice info for the group  
            groupinfo[<groupid>]['slices']['used'] - the number of slices used (integer)
            groupinfo[<groupid>]['slices']['total'] - the total number of slices in group (integer)
            groupinfo[<groupid>]['sservers'] - an array containing the slice servers in the group (strings)
            groupinfo[<groupid>]['sliceservers'] - dictionary containing detailed slice server info for each slice server
            groupinfo[<groupid>]['sliceservers'][<ssid>]['serialno'] - the serial number of the shelf (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['model'] - the model number of the physical shelf (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['proto'] - Not sure what this is (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['ip'][<ipaddr>]['speed'] - speed in mbps (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['ip'][<ipaddr>]['RPCs'] - nnnnn:n (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['ip'][<ipaddr>]['errors'] - n:n (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['bytealloc']['used'] - used bytes (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['bytealloc']['total'] - total bytes (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['bytealloc']['usedGB'] - used bytes in GB (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['bytealloc']['totalGB'] - total bytes in GB (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['slices'] - number of slices (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['slicesready'] - percent of slices ready  (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['replicates']['queued'] - replicate slices queued (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['replicates']['launched'] - replicate slices launched (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['replicates']['pending'] - replicate slices pending (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['replicates']['done'] - replicate slices done (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['replicates']['migrating'] - replicate slices migrating (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['iobandwidth'] - io bandwidth in Mb/s  (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['slice']['ios'] - slice I/Os (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['slice']['errors'] - count of error in slice I/Os (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['slice']['reads'] - slice reads count (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['slice']['writes'] - slice writes count (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['slice']['deletes'] - lost slices count (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['errors']['reads'] - read errors count (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['errors']['writes'] - write errors count (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['errors']['lost'] - lost errors count (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['rss']['percent'] - rss percentage (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['rss']['total'] - rss total (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['rss']['free'] - rss free (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['scache']['percent'] - scache percentage (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['scache']['total'] - scache total (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['scache']['free'] - scache free (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['ioq']['metric'] - ioq metric (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['ioq']['depth'] - ioq depth (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['ioq']['delay'] - ioq delay (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['loadaverages'] - array of 3 load averages containing integer values
            groupinfo[<groupid>]['sliceservers'][<ssid>]['sliced'] - sliced status (OK, READ-DELETE, EVACUATING) (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['stability'] - OK or ??? (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['access'] - ONLINE or ??? (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['monitor'] - RECONCILE or ??? (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['discovered'] - nnnnnn:nn:nn:nn.nnn ???  (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['probed'] - nnnnnn:nn:nn:nn.nnn ???  (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['probes'] - nnnn probe count ???  (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['evacuation']['status'] - evacuation status (string)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['evacuation']['counter']['slicesdone'] - number of slices evacuated (integer)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['evacuation']['counter']['totalslices'] - total number of slices to evacuate (integer)
         if shelf evacuation is running:
            ssinfo['evacuation']['percentcomplete'] = percent of evacuation complete (string)
            ssinfo['evacuation']['slicespersec'] = slices evacuated per second (integer)
            ssinfo['evacuation']['datetime'] = date time ??? (string)
         if evacuation has been run there will be additional information:
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Stage']['avg'] - average ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Stage']['min'] - minimum ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Stage']['max'] - maximum ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Submit']['avg'] - average ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Submit']['min'] - minimum ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Submit']['max'] - maximum ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Launch']['avg'] - average ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Launch']['min'] - minimum ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Launch']['max'] - maximum ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Launch']['missed'] - missed ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Complete']['avg'] - average ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Complete']['min'] - minimum ??? (float)
            groupinfo[<groupid>]['sliceservers'][<ssid>]['Complete']['max'] - maximum ??? (float)
        
        if there is a problem parsing any of the lines a warning is logged, and the 
        lines continue to be processed     
        
        '''
        ssinfo = {}
        ginfo = {}
        ssid = None 
        gid = None       
        
        
        s1 = re.compile("\sSSID[\=\~](\d+)\s+(.*)")
        g1 = re.compile("GID=(\d)\s(.*)")
        for line in output:
            line = line.rstrip()
            self.testlog.info("processing line: %s" % line)

            m = g1.match(line)
            if m:
            # processing group info
                (gid, parameters) = m.groups()
                if gid not in ginfo.keys():
                    ginfo[gid] = {}
                    ginfo[gid]['sliceservers'] = {}
                if "SSID" in parameters:
                    sservers = parameters.split(" ")
                    ginfo[gid]['sservers'] = sservers
                    for ss in ginfo[gid]['sservers']:
                        if ss == " ": ginfo[gid]['sservers'].remove(ss)
                        if ss == "SSID:": ginfo[gid]['sservers'].remove(ss)
                    continue
                # the following processes line with key=value strings
                (key,value) = parameters.split("=")
                if "servers" in parameters:
                    ginfo[gid]['servercount'] = int(value)
                    continue
                if "bytes allocation" in key:
                        ginfo[gid]['byteallocation'] = {}
                        parts = value.split("/")
                        ginfo[gid]['byteallocation']['used'] = int(parts[0]) 
                        ginfo[gid]['byteallocation']['total'] = int(parts[1])
                        continue
                if "slices" in parameters:
                    ginfo[gid]['slices'] = {}
                    parts = value.split('/')
                    ginfo[gid]['slices']['used'] = int(parts[0]) 
                    ginfo[gid]['slices']['total'] = int(parts[1])
                    continue
            m = re.match(s1,line)
            if not m:
                self.testlog.warning(\
                "oops: didn't get the parameters from line:\n%s" % line)
                continue
            # processing slice server info
            (id,parameters) = m.groups()
            if not ssid:
                ssid = id
                ssinfo = {}
            elif ssid != id:
                ginfo[gid]['sliceservers'][ssid] = {}
                ginfo[gid]['sliceservers'][ssid].update(ssinfo)
                ssid = id
                ssinfo = {}
            if "SN=" in parameters:
                m = re.match("SN=(.*)\sMODEL=(.*)\sIP=(.*)PROTO=(\d+)",parameters)
                if not m:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                params = m.groups()
                ssinfo['serialno'] = params[0]
                ssinfo['model'] = params[1]
                ssinfo['proto'] = params[3]
                ipaddrs = params[2].split(" ")
                ssinfo['ip'] = {}
                for ipaddr in ipaddrs:
                    if ipaddr != ' ' and ipaddr != '':
                        ssinfo['ip'][ipaddr] = {}
                continue
            if "byte allocation" in line:
                ssinfo['bytealloc'] = {}
                params = re.findall("\d+",parameters)
                if not params:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                ssinfo['bytealloc']['used'] = int(params[0])
                ssinfo['bytealloc']['total'] = int(params[1])
                ssinfo['bytealloc']['GBused'] = int(params[2])
                ssinfo['bytealloc']['GBtotal'] = int(params[3])
                continue
            if "slices=" in parameters:
                #slices=3885808 ready=100%
                m = re.match("slices=(\d+)\sready=([\d\%]+)",parameters)
                if not m:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                (ssinfo['slices'],ssinfo['slicesready']) = m.groups()
                ssinfo['slices'] = int(ssinfo['slices'])
                continue
            if "replicates" in parameters:
                params = re.findall("\d+",parameters)
                if not params:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                ssinfo['replicates'] = {}
                ssinfo['replicates']['queued'] = int(params[0])
                ssinfo['replicates']['pending'] = int(params[1])
                ssinfo['replicates']['launched'] = int(params[2])
                ssinfo['replicates']['done'] = int(params[3])
                ssinfo['replicates']['migrating'] = int(params[4])
                continue
            if 'evacuation' in parameters:
                params = re.findall("=([\w\/]+)",parameters)
                if not params:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                ssinfo['evacuation'] = {}
                ssinfo['evacuation']['status'] = params[0]
                if params[0] == "IDLE": continue
                ssinfo['evacuation']['counter'] = {}
                parts = params[1].split("/")
                ssinfo['evacuation']['counter']['slicesdone'] = int(parts[0])
                ssinfo['evacuation']['counter']['totalslices'] = int(parts[1])
                m = re.search("([\d\%]+)\s([\d\.]+)\sslices\/sec\s(.*)",parameters)
                if not m:
                    self.testlog.warning("unable to get params from line:\n%s",
                                         line)
                    continue
                params = m.groups()
                ssinfo['evacuation']['percentcomplete'] = params[0]
                ssinfo['evacuation']['slicespersec'] = params[1]
                ssinfo['evacuation']['datetime'] = params[2]
                continue
            if 'ioBandwidth' in parameters:
                m = re.search("(\d+)",parameters)
                
                ssinfo['iobandwidth'] = m.groups()[0]
                ssinfo['iobandwidth'] = int(ssinfo['iobandwidth'])
                continue
            if "slice " in parameters:
                if 'slice' not in ssinfo: ssinfo['slice'] = {}
                m = re.findall("(\w+=\d+)",line)
                for item in m:
                    (key,value) = item.split("=")
                    ssinfo['slice'][key] = int(value)
                continue
            if "error " in parameters:
                ssinfo['error'] = {}
                m = re.findall("(\w+=\d+)",line)
                for item in m:
                    (key,value) = item.split("=")
                    ssinfo['error'][key] = int(value)
                continue
            if "rss=" in parameters or 'scache' in parameters:
                if 'scache' in parameters:
                    key = 'scache'
                else:
                    key = 'rss'
                params = re.findall("=(\d+)",parameters)
                if not params:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                ssinfo[key] = {}
                ssinfo[key]['percent'] = params[0]
                ssinfo[key]['total'] = int(params[1])
                ssinfo[key]['free'] = int(params[2])
                    
            if "sliced" in parameters or "probed" in parameters:
                m = re.findall("(\w+=[\d\w:<>-]+)",line)
                if not m:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                for item in m:
                    (key,value) = item.split("=")
                    ssinfo[key] = value
                continue
            if "ioq " in parameters:
                ssinfo['ioq'] = {}
                m = re.findall("(\w+=\d+)",line)
                if not m:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                for item in m:
                    (key,value) = item.split("=")
                    ssinfo['ioq'][key] = int(value)
                continue
            if "load averages" in parameters:
                params = re.findall("\d+",parameters)
                ssinfo['loadaverages'] = params
                continue
            if "speed" in parameters:
                stuff = {}
                m = re.findall("(\w+=[\d\.\:]+)",line)
                if not m:
                    self.testlog.warning(\
                    "oops: didn't get the parameters from line:\n%s" % line)
                    continue
                for item in m:
                    (key,value) = item.split("=")
                    stuff[key] = value
                ssinfo['ip'][stuff['IP']].update(stuff)
                continue
            m = re.search("(Stage|Submit|Launch|Complete):",line)
            if m:
                thekey = m.groups()[0]
                ssinfo[thekey] = {}
                stuff = re.findall('(\w+)\=\s*([\d.]+)\s*',line)
                for item in stuff:
                    if item[0] == "SSID": continue
                    ssinfo[thekey][item[0]] = float(item[1])
#         print "ssinfo for",ssid,":\n",ssinfo
        if len(ssinfo) > 0:
            ginfo[gid]['sliceservers'][ssid] = {}
            ginfo[gid]['sliceservers'][ssid].update(ssinfo)
        return ginfo        
        
           
                       

    def AddDictionary(self,myobject):
        '''Adds the items in a dictionary to the cld object'''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        for item in myobject:
            setattr(self,item,myobject[item])
             
          
    def whatami(self):
        ''' gets the device id (the model of the cld'''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        output,error = MGComm.sendsshcmd(self.ssh,"whatami")
        if error:
            self.testinfo.error = "%s unable to get whatami\
                                     for %s: %s" %\
                thisfunc,self.hostname,error
            return -1
        return output[0]
         
     
    def GetClusterName(self):
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        output,error = MGComm.sendsshcmd(self.ssh,"hostname")
        if error:
            self.testinfo.error = "%s unable to get hostname for %s: %s" % \
                (thisfunc,self.hostname,error)
            return -1
        myname = re.sub("-\d*$","",output[0])
        self.testlog.debug(thisfunc + ": returning " + myname)
        return myname
     
    def DelayIOHelper(self,delaytime):
        ''' sets the delay time for the IO helper, this is to
        facilitate certain filesystem testing'''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        commands = ['echo "set ioHelperDelayTime=' + delaytime + '" > /tmp/cmd',
                    'echo "q" >> /tmp/cmd',
                    "gdb -p `cat /var/run/mdscore.pid` -x /tmp/cmd"]
        count = 0
        for command in commands:
            count += 1
            output,error = MGComm.sendsshcmd(self.ssh,command)
            if error:
                self.testinfo.error = "%s unable to set IOHelper delay for %s: %s" % \
                    (thisfunc,self.hostname,error)
                return -1
            if count == len(commands):
                foundit = 0
                for line in output:
                    if "The program is running" in line:
                        foundit = 1
                        break
                if not foundit:
                    self.testinfo.error = "%s: unable to set iohelper delay. result: \n" % \
                        thisfunc
                    self.testinfo.error = self.testinfo.error + ''.join(str(e) for e in output)
                    return -1
        return 0
     
    def GetACL(self,obj,mytype)
        ''' gather the acls from the mdsclientn on the cld'''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        if not mytype: mytype = "e"
        if mytype == "e":
            cmd = '/opt/omcld/bin/mdsclientn -c "acl geteffect ' + obj + '"'
        else:
            cmd = '/opt/omcld/bin/mdsclientn -c "acl get ' + obj + '"'
         
        cmd = cmd + " -u ******** -p *** " + self.ip['public'][0]
                   
        self.testlog.debug("%s: sending command: %s",thisfunc,cmd)
        output,error = MGComm.sendsshcmd(self.ssh, cmd)
        if error:
            self.testinfo.error = "%s unable to get acl for %s: %s" % \
                (thisfunc,self.hostname,error)
            return -1
         
        acl = self.parseacl(output)
        return acl
    
        
     
     
    def GetAuthenticationGroups(self):
        '''get an array of groups from the grid
        note: static proprietary user name and password are change to
        protect the innocent
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        command = "/opt/omcld/bin/fstest -u ***** -p *** localhost getgroups"
        output,error = MGComm.sendsshcmd(self.ssh,command)
        print thisfunc + " output:", output
        print thisfunc + " error: ", error
        if error:
            self.testlog.error(error)
            return -1
        groups = {}
        firstline = 1
        for line in output:
            if re.match("\d\d\-\d\d\-\d\d\s",line): continue
            line.strip()
            if firstline:
                errorlist = ['unable','cannot','busy','timeout','no mem','no connect',"invalid","RPC"]
                firstline = 0
                for mystr in errorlist:
                    if re.search(mystr,line,re.IGNORECASE):
                        self.testlog.error("%s: unable to get groups: %s",self.hostname,line)
                        return -1
            print "processing: " + line
            parts = line.split(": ")
            print thisfunc,"parts: ", parts
            groups[parts[0]] = parts[1]
        return groups
             
             
     
    def GetUsers(self):
        '''get an array of users from the grid
        note: static proprietary user name and password are change to
        protect the innocent
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        self.testlog.debug("%s: starting",self.hostname)
        command = "/opt/omcld/bin/fstest -u ****** -p *** localhost getusers"
        output,error = MGComm.sendsshcmd(self.ssh,command)
        if error:
            self.testlog.error(error)
            return -1
        users = {}
        firstline = 1
        for line in output:
            m = re.match("\d\d\-\d\d\-\d\d\s",line)
            if m:
                print thisfunc,"skipping line:",line 
                continue
            line.strip()
            if firstline:
                firstline = 0
                errorlist = ['unable','cannot','busy','timeout','no mem','no connect',"invalid","RPC"]
                for mystr in errorlist:
                    if re.search(mystr,line,re.IGNORECASE):
                        self.testlog.error("%s: unable to get users: %s",self.hostname,line)
                        return -1
 
            print thisfunc,"processing: " + line
            parts = line.split(": ")
            print thisfunc,"parts: ", parts
            users[parts[0]] = parts[1]
        return users
     
    def getname(self,sid)
        'gets the name for the  security id (sid)'
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        name = None
        if sid == 'all': return sid
        groups = getattr(self,"groups",None)
        users = getattr(self,"users",None)
        if groups == None:
            groups = self.GetAuthenticationGroups()
        if users == None:
            users = self.GetUsers()
        objs = []
        objs.extend(groups)
        objs.extend(users)
        for obj in objs:
            if sid in obj:
                name = re.search('(.*)\:\s',obj)
                break
        return name
         
     
    def parseacl(self,output):
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        marker = None
        acl = {}
        for line in output:
            line.strip()
            if line == "":
                continue
            if "Opened default session" in line:
                marker = 1
                continue
            if not marker: continue
            if "Closing session" in line: break
            parts = line.split(",")
            perms = re.search("\s*(\d+)\: (\w+)",parts[0])
            myid = perms[0]
            perm = perms[1]
            acl[myid] = {}
            acl[myid]['perm'] = perms
            parts1 = re.sub('\{|\}','',parts[1])
            ops = re.findall("(\w+)\s",parts1)
            acl[myid]['ops'] = ops
            sid = parts[2]
            name = self.getname(sid)
            acl[myid]['sid'] = sid
            acl[myid]['name'] = name
            acl[myid]['ace'] = line
        opsary = ["read","write","exec","sysdata","userdata","list","create",
               "delete","rename"]
        for ace in acl:
            acl[ace]['allow'] = []
            acl[ace]['deny'] = []
            perm = acl[ace]['perm']
            for op in opsary:
                foundit = 0
                for myop in acl[ace]['ops']:
                    if myop == "sysmetadata" and op == 'sysdata':
                        foundit = 1
                        break
                    elif myop != op:
                        continue
                    foundit += 1
                    break
                if foundit > 0:
                    if perm == "allow":
                        if 'perms' not in acl[ace]: acl[ace]['perms'] = {}
                        acl[ace]['perms'][op] = 1
                        acl[ace]['ace']['allow'].append(op)
                    else:
                        acl[ace]['ace']['deny'].append(op)
                        if 'perms' not in acl[ace]: acl[ace]['perms'] = {}
                        acl[ace]['perms'][op] = 0
                else:
                    if 'perms' not in acl[ace]: acl[ace]['perms'] = {}
                    acl[ace]['perms'][op] = "I"
        return acl
             
    def WaitForRestart(self,timeout,monq):
        '''
        # note that ths is similiar to IsFSUp but the mdscore log monitor has been up
        # since just prior to killing the mdscore so it looks for several indicators as
        # mdscore comes up.  Thus in case of failure it will be easier to pinpoint the
        # problem by logging the status of the journal, sliceserver and the FS becoming
        # available
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        foundit = 0
        start = 1
        steady = 2
        ssminit = 3
        ready = 4
        startcount = 0
        ssmipcerr = 0
        startretries = 0;
        while (time.time() - self.starttime) < timeout:
            if monq.empty():
                sleep(2)
                continue
            else:
                msg = monq.get_nowait()
                print "%s:%s got message: %s" % (thisfunc,self.hostname,msg)
            if 'Starting MDS core server' in msg:
                print "%s:%s found Starting MDS core server" % (thisfunc,self.hostname)
                startcount += 1
                foundit = start
                if startcount > 1:
                    if ssmipcerr:
                        ssmipcerr = 0
                        startretries += 1
                        foundit = 0
                        continue
                    error = "%s:%s mdscore logged unexpected restart:\n%s" \
                        % (thisfunc,self.hostname,msg)
                    self.testlog.error(error)
            elif "SSM is initialized" in msg:
                print "%s:%s found ssminit" % (thisfunc,self.hostname) 
                foundit = ssminit
            elif "signalWaitHandle" in msg:
                if "Waiting for signals" not in msg: continue
                if foundit != ssminit: continue
                print "%s:%s found waiting for signals" % (thisfunc,self.hostname) 
                foundit = ready
                pat = re.compile(r'(.*)\.\d+\|')
                try:
                    self.uptime = pat.match(msg).groups()[0]
                except:
                    pass
                self.testlog.debug("%s:%s uptime is %s",thisfunc,self.hostname,self.uptime)
                # TODO:  need to get the epoch value of uptime
            elif "oujourStateChange" in msg:
                if "DEAD" in msg:
                    self.testinfo.error = "%s:%s mdscore failed to start up\n\t\t%s" \
                        % (thisfunc,self.hostname,msg)
                elif "STEADY" in msg:
                    print "%s:%s found STEADY" % (thisfunc,self.hostname)
                    foundit = steady
            elif "ssmIpcError" in msg:
                print "%s:%s found ssmIpcError" % (thisfunc,self.hostname)
                ssmipcerr += 1
            elif "|E|" in msg:
                if re.search("shutdown|sync|read val|1048594|1048583",msg):
                    print "%s:%s found error... ignoring" % (thisfunc,self.hostname)
                    continue
                else:
                    print "%s:%s found error... reporting" % (thisfunc,self.hostname)
                    error = "%s: error occurred during restarting mdscore:\n%s" % (self.hostname,msg)
                    self.testinfo.error(msg)
            if foundit == ready or self.testinfo.error: break
        if self.testinfo.error: return -1
         
        if foundit == ready:
            duration = time.time() - self.starttime
            self.testinfo.testlog.info("%s: mdscore started with %d retries duration: %d seconds",\
                                       self.hostname,startretries,duration)
            return 0
        if not foundit:
            self.testinfo.error = "%s:%s mdscore did not log 'Starting MDS core server' after %d seconds" \
                % (thisfunc,self.hostname,timeout)
        elif foundit == start:
            self.testinfo.error = \
                "%s:%s mdscore did not log state change from RECOVER -> STEADY after %d seconds" \
                % (thisfunc,self.hostname,timeout)
        elif foundit == steady:
            self.testinfo.error = \
                "%s:%s mdscore did not log 'SSM is initialized' after %d seconds" \
                % (thisfunc,self.hostname,timeout)
        self.testinfo.errortype = "ERROR"
        return -1
     
    def getgrepresult(self,outp,mystr):
        '''
        # Method: _getGrepResult
        # Scope: PRIVATE
        # Status: Complete
        # Description: parses the grep output to find the specified string.
        # Input Parameters
        #  mystr - REQUIRED - the string to search for
        #  $outp - REQUIRED - an ref to the grep output array
        # Output:
        # if not found returns None
        # on success: returns the string found
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        foundit = 0
        for line in outp:
            if mystr in line:
                self.testinfo.testlog.debug("%s:%s returning %s",thisfunc,self.hostname,line)
                line.strip()
                return line
        self.testinfo.testlog.debug("%s:%s returning None",thisfunc,self.hostname)
        return None
         
         
 
         
     
    def GetPID(self,proc):
        '''
        # Method: GetPID
        # Scope: PUBLIC
        # Status: Complete
        # Description: get the PID for a specified process
        # Input Parameters
        #  self - REQUIRED - the ContentDirector object
        #  proc - REQUIRED - the process to search for
         
        # Output:
        #   on success: returns the pid for the process
        #   on failure: returns -1 if not found.
        #              $test->{errortype} contains the error type
        #              $test->{errormsg} contains the error message
        '''
                     
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        command = "ps -e|grep " + proc
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            self.testinfo.error = "%s:%s unable to get pid for %s: %s" % \
                (thisfunc,self.hostname,proc,error)
            self.testlog.debug(self.testinfo.error + " returning -1")
            return -1
        line = self.getgrepresult(output, proc)
        if line == None:
            self.testlog.debug("%s:%s returning None",thisfunc,self.hostname) 
            return None
        m = re.match('^\s*(\d+)',line)
        if not m:
            self.testlog.debug("%s:%s returning None",thisfunc,self.hostname)
            return None
        pid = m.group()
        self.testlog.debug("%s:%s returning %s",thisfunc,self.hostname,pid)
        return pid 
                 
    def KillMDS(self,*args):
        '''
        # Method: KillMDS
        # Scope: PUBLIC
        # Status: Complete
        # Description:
        #   kills the mds process. if wait is 1 we wait until the mdscore starts up
        #   and signalWaitHandle is logged to the mdscore log.
        #   returns error if:
        #       the proceess does not restart with new pid in 3 seconds
        #       if wait is 1, error if signalWaitHandle is not found within 10 minutes
        #       any other COMM error
        # Input Parameters:
        #     self - REQUIRED - the cld object
        #     opts - OPTIONAL - hash containing the following parameters:
        #         wait - OPTIONAL - if set we wait for the cld to come back up default is wait = 1
        #         timeout - OPTIONAL - the max time to wait for mds to come up completely
        #                        in seconds. -1 means on't wait.
        # Output:
        #   on success:  return 0
        #   on failure: returns -1 and self.testinfo.error contains the error
        # Notes:
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
 
        wait = None
        rc = 0
        timeout = 1800
        wait = 1
        if len(args) > 0:
            opts = args[0]
            if "wait" in opts: wait = opts['wait']
            if "timeout" in opts: timeout = opts['timeout']
         
        if wait:
            monq = self.monitors['mdscore'].addwriteq()
            reportlist = ["oujourStateChange","SSM is initialized",
                          "signalWaitHandle","Starting MDS core server"]
            ignorelist = ["starting RPC thread shutdown"]
            self.monitors['mdscore'].reportlist_add(reportlist)
            self.monitors['mdscore'].ignorelist_add(ignorelist)
        oldpid = self.GetPID("mdscore")
        if oldpid == None:
            self.testinto.error = "%s:%s unable to get the pid for mdscore" % (thisfunc,self.hostname)
            return -1
        sleep(3)
        command = "kill -9 " + oldpid
        output,error = MGComm.sendsshcmd(self.ssh,command)
        if error:
            self.testinfo.error = "%s unable to kill pid on %s: %s" % \
                    (thisfunc,self.hostname,error)
            return -1
        setattr(self,"starttime",time.time())
 
        newpid = None
        retries = 0
        while newpid == None:
            newpid = self.GetPID("mdscore")
            if newpid == None or newpid == oldpid:
                newpid = None
                if retries == 3: break
                retries += 1
                sleep(5)
        if newpid:
            if wait:
                rc = self.WaitForRestart(timeout, monq)
        if "delayiohelper" in self.testinfo.settings: 
            self.DelayIOHelper(self.testinfo.settings['delayiohelper'])
        if wait:
            self.monitors['mdscore'].removewriteq(monq)
            self.monitors['mdscore'].ignorelist_remove(ignorelist)
            self.monitors['mdscore'].reportlist_remove(reportlist)
        return rc
         
    def StartCLDServices(self,*args):
        ''' stops the cld services of the cld defined in self.
        # Description: start the omcld services, check the status of the services
        # and reports an error if all of the services did not come back up. If the
        # wait variable is set, we monitor the cld via _WaitForRestart until the
        # file system on the cld is online or we timeout (default 3600 second).
        # If the file system is not up within the timeout, we report an error.
        # Input Parameters
        #    opts - OPTIONAL - hash containing the following options:
        #        wait - OPTIONAL - wait for the cld's file system to come back online
        #            default no wait.
        #        timeout - OPTIONAL - the time out for waiting for the cld's file system
        #            to come back online if we are waiting.  default 3600 seconds
        #        monitor - OPTIONAL - reference to the mdscore monitor.  Not needed if
        #            we are not waiting.  Not needed if the monitor is stored in
        #            self->{monitors}->{mdscore}
        # Output:
        # on error return -1 with error in self.test['error', self.test['errortype']
        # on success: returns 0
        #    self.starttime - the time we restarted the cld
        #   if opts['wait'] = 1:
        #    self.uptime - the date/time string from the mdscore log line containing
        #                signalWaitHandle Waiting for signals
        #    self.euptime - the epoch time from the mdscore log line containing
        #                signalWaitHandle Waiting for signals
        # NOTE: if we don't wait, success is defined as all the omcld services running
        # if we do wait, success is defined as all of the omcld services running and
        # the file system on the cld is back online. '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        if len(args):
            opts = args[0]
        if opts and opts.has_key('timeout'):
            timeout = opts['timeout']
        else:
            timeout = 3600
        if opts and opts.has_key('wait'):
            wait = opts['wait']
        else:
            wait = 0
 
        if wait:
            reportlist = ["oujourStateChange","SSM is initialized",
            "signalWaitHandle","Starting MDS core server","ssmIpcError"]
            self.monitors['mdscore'].reportlist_add(reportlist)
            wq = self.monitors['mdscore'].addwriteq()
             
        command = "service omcld start"
        output,error = MGComm.sendsshcmd(self.ssh,command)
        if error:
            self.testinfo.error = "%s unable to start services on %s: %s" % \
                    (thisfunc,self.hostname,error)
            return -1
        
 
         
        setattr(self,"starttime",time.time())
        retries = 0
        while True:
            sleep(30)
            cldstatus = self.GetCLDStatus()
            if cldstatus['status'] == 'running': break
            retries += 1
            if retries > 3:
                self.testnfo.error = "%: unable to start omcld server on %s.  Status is %s" \
                  % (thisfunc,self.hostname,cldstatus['status'])
                return -1
        rc = 0
        if wait:
            rc = self.WaitForRestart(timeout,wq)
            self.monitors['mdscore'].removewriteq(wq)
            if not rc and "delayiohelper" in self.testinfo.settings: 
                self.DelayIOHelper(self.testinfo.settings['delayiohelper'])
 
        return rc
     
    def StopCLDServices(self):
        '''# Method: StopCLDServices
        # Scope: PUBLIC
        # Status: Complete
        # Description: stop the omcld services
        # Input Parameters
        #  self - REQUIRED - the ContentDirector object
        # Output:
        # on error return -1 with error in $test->{errormsg}, $test->{errortype}
        # on success: returns 0 '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        command = "service omcld stop"
        output,error = MGComm.sendsshcmd(self.ssh,command)
        if error:
            self.testinfo.error = "%s unable to start services on %s: %s" % \
                    (thisfunc,self.hostname,error)
            return -1
        sleep(10)
        cldstatus = self.GetCLDStatus()
        if cldstatus['status'] != "stopped":
            self.testinfo.error = "%s:%s unable to stop omcld services.  Status is %s." \
                % (thisfunc,self.hostname,cldstatus['status'])
            self.testlog.debug("%s:%s error: %s returning -1",thisfunc,self.hostname,self.testinfo.error)
            return -1
        return 0
     
     
    def CheckForCores(self,starttime):
        '''looks for cores that were created after the start time and scp them 
           to the log directory'''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("%s: starting",self.hostname)
        command = "ls -1 /var/anonymous/debug/core*"
        output,error = MGComm.sendsshcmd(self.ssh, command)
        if error:
            self.testinfo.error = "%s unable to start services on %s: %s" % \
                    (thisfunc,self.hostname,error)
            return -1
        for line in output:
            line.strip()
            corefile = '/var/anonymous/debug/' + line
            coretime = time.ctime(os.path.getctime())
            if coretime > starttime:
                self.testlog.error("Core file found: " + line)
                MGComm.scpget(self.ssh, corefile)
                target = self.testinfo.log['logdir'] + "/"  + line
                shutil.move(line,target)
        return 0



#  this is the test code for this class
testlog = None
testinfo = None
cld = None
import types


def testcase_GetSSGroupInfo_1():
    global cld, testlog, testinfo
    testlog.info("Assertion: Get basic slice server group information succeeds")
    ginfo = cld.GetSSGroupInfo(None)
    if ginfo == -1 or ginfo == None:
        testlog.error("test failed:\n\t\t ginfo = %s" % str(ginfo))
        return 0
    keys = { 'TB': { "total": types.FloatType, "used": types.FloatType },
            "id": types.IntType,
            'servercount': types.IntType,
            'slicecount': types.IntType,
            'servers': types.ListType,
            'status': types.StringType,
            }
    for gid in ginfo:
        testlog.info("processing group %s" % gid)
        for key in keys:
            if key not in ginfo[gid].keys():
                testlog.error("ginfo for group %s does not contain the key %s" % (gid,key))
                continue
            
            if type(keys[key]) == types.DictType:
                if type(ginfo[gid][key]) == types.DictType:
                    for key2 in keys[key]:
                        if key2 not in ginfo[gid][key].keys():
                            testlog.error("ginfo for group %s does not contain [%s][%s]" % (gid,key,key2))
                        elif type(ginfo[gid][key][key2]) != keys[key][key2]:
                            testlog.error("ginfo for group %s [%s][%s] should be %s instead of %s" \
                            % (gid, key, key2, keys[key][key2], type(ginfo[gid][key][key2])))
                else:
                    testlog.error("ginfo for group %s: %s should be %s instead of %s") \
                      % (gid,key,types.DictType,type(ginfo[gid][key]))
                continue
            if type(ginfo[gid][key]) != keys[key]:
                testlog.error("ginfo for group %s: %s should be %s instead of %s" \
                      % (gid, key, keys[key], type(ginfo[gid][key])))
    testinfo.LogDict(ginfo)
    return 0

def reportGroupError(msg,ckeys):
    global cld, testlog, testinfo
    mymsg = "%s: %s: " % (cld.hostname,msg)
    for item in ckeys:
        mymsg = mymsg + "['%s']" % item
    testlog.error(mymsg)
        
def testcase_GetSSGroupInfo_2():
    global cld, testlog, testinfo
    testlog.info("Assertion: Get detailed information for slice server groups succeeds")
    ginfo = cld.GetSSGroupInfo("-1")
    if ginfo == -1 or ginfo == None:
        testlog.error("test failed:\n\t\t ginfo = %s" % str(ginfo))
        return 0
    keys = {'sservers': types.ListType,
             'sliceservers': 
                {'serialno': types.UnicodeType,
                 'iobandwidth': types.IntType,
                 'discovered': types.UnicodeType,
                 'slices': types.IntType,
                  u'probed': types.UnicodeType,
                  'ip': { 'variable': 
                            {u'IP': types.UnicodeType,
                            u'errors': types.UnicodeType,
                            u'speed': types.UnicodeType,
                            u'RPCs': types.UnicodeType},
                        },
                  'error': {
                        u'reads': types.IntType,
                        u'writes': types.IntType,
                        u'lost': types.IntType
                        },
                  u'Submit': {
                        u'max': types.FloatType,
                        u'avg': types.FloatType,
                        u'min': types.FloatType
                        },
                  u'sliced': types.UnicodeType,
                  'ioq': {
                        u'delay': types.IntType,
                        u'metric': types.IntType,
                        u'depth': types.IntType
                        },
                  u'probes': types.UnicodeType,
                  'bytealloc': {
                        'total': types.IntType,
                        'GBtotal': types.IntType,
                        'used': types.IntType,
                        'GBused': types.IntType
                        },
                  'slice': {
                        u'reads': types.IntType,
                        u'errors': types.IntType,
                        u'ios': types.IntType,
                        u'writes': types.IntType,
                        u'deletes': types.IntType
                        },
                  u'Complete': {
                        u'max': types.FloatType,
                        u'avg': types.FloatType,
                        u'min': types.FloatType
                        },
                  'scache': {
                        'total': types.IntType,
                        'percent': types.UnicodeType,
                        'free': types.IntType
                        },
                  'proto': types.UnicodeType,
                  u'Launch': {
                        u'max': types.FloatType,
                        u'avg': types.FloatType,
                        u'missed': types.FloatType,
                        u'min': types.FloatType
                        },
                  u'monitor': types.UnicodeType,
                  'replicates': {
                        'migrating': types.IntType,
                        'launched': types.IntType,
                        'done': types.IntType,
                        'queued': types.IntType,
                        'pending': types.IntType},
                  u'access': types.UnicodeType,
                  'loadaverages': types.ListType,
                  'slicesready': types.UnicodeType,
                  u'stability': types.UnicodeType,
                  'evacuation': {
                      'status': types.UnicodeType
                      },
                  'model': types.UnicodeType,
                  'rss': {
                        'total': types.IntType,
                        'percent': types.UnicodeType,
                        'free': types.IntType
                        },
                  u'Stage': {
                        u'max': types.FloatType,
                        u'avg': types.FloatType,
                        u'min': types.FloatType
                        }
                },
         'servercount': types.IntType,
         'byteallocation': {
            'total': types.IntType,
            'used': types.IntType
            },
         'slices': {
            'total': types.IntType,
            'used': types.IntType
            }
        }
    
    ckeys = []
    for gid in ginfo:
        testlog.info("processing group %s" % gid)
        ckeys.append(gid)
        for key in keys:
            ckeys.append(key)
            print "processing :",ckeys
            if key not in ginfo[gid].keys():
                reportGroupError('1 key missing',ckeys)
            elif key == "sliceservers": 
                checkSliceServerInfo(keys,ginfo[gid]['sliceservers'],ckeys)
            elif type(keys[key]) == types.DictType:
                if type(ginfo[gid][key]) == types.DictType:
                    for key2 in keys[key]:
                        ckeys.append(key2)
                        print "processing :",ckeys
                        if key2 not in ginfo[gid][key].keys():
                            reportGroupError('2 key missing',ckeys)
                        elif type(ginfo[gid][key][key2]) != keys[key][key2]:
                            msg = "3 incorrect key type should be %s instead of %s" \
                              % (keys[key][key2], type(ginfo[gid][key][key2]))
                            reportGroupError(msg, ckeys)
                        ckeys.pop()
                else:
                    msg = "4 incorrect key type should be %s instead of %s" \
                      % (types.DictType,type(ginfo[gid][key]))
                    reportGroupError(msg, ckeys)
            elif type(ginfo[gid][key]) != keys[key]:
                msg = "5 incorrect key type should be %s instead of %s" \
                  % (keys[key], type(ginfo[gid][key]))
                reportGroupError(msg, ckeys)
            ckeys.pop()
        ckeys.pop()
    testinfo.LogDict(ginfo)
    return 0

def checkSliceServerInfo(keys,ssinfo,ckeys):
    global cld, testlog, testinfo
    sskeys = keys['sliceservers']
    for ssid in ssinfo:
        ckeys.append(ssid)
        print "processing :",ckeys
        for key in sskeys.keys():
            ckeys.append(key)
            print "processing: ",ckeys
            if key not in ssinfo[ssid]:
                reportGroupError("6 missing key", ckeys)
            elif type(sskeys[key]) == types.DictType:
                print "sending to checkDictionary: ",sskeys[key],"\n",ssinfo[ssid][key]
                checkDictionary(sskeys[key], ssinfo[ssid][key], ckeys)
            elif type(ssinfo[ssid][key]) != sskeys[key]:
                msg = "7 incorrect key type should be %s instead of %s" \
                  % (sskeys[key], type(ssinfo[ssid][key]))
                reportGroupError(msg, ckeys)
                
            ckeys.pop()
        ckeys.pop()
        
                
            
def checkDictionary(keys,mydict,ckeys):
    global cld, testlog, testinfo
    for key in keys.keys():
        ckeys.append(key)
        print "processing: ",ckeys
        if key == "variable":
            for item in mydict:
                ckeys.append(item)
                print "processing: ",ckeys
                checkDictionary(keys[key], mydict[item], ckeys)
                ckeys.pop()
        elif key not in mydict:
            reportGroupError("8 key missing", ckeys)
        elif keys[key] == types.DictType:
            checkDictionary(keys[key], mydict[key], ckeys)
        elif type(mydict[key]) != keys[key]:
            msg = "9 incorrect key type should be %s instead of %s" % (keys[key],type(mydict[key]))
            reportGroupError(msg, ckeys)
        ckeys.pop()
        

    
    


testcases = {
        'testcase_GetSSGroupInfo_1': { 'title': "Get basic slice server group information succeeds",
                                       'func': testcase_GetSSGroupInfo_1 },
        'testcase_GetSSGroupInfo_2': { 'title': "Get detailed information for slice server groups succeeds",
                                       'func': testcase_GetSSGroupInfo_2 },
    }

    
    
def TestSetup():
    '''Setup test environment and variables'''
    global testinfo
    global testlog
    global testcases
    global cld
    
    opts = {
        'gridmonitor' : { 'value' : 1, 'required' : 0,'type' : "int" },
        'gridip'      : { 'value' : None, 'required' : 1,'type' : "str" },
        'interactive' : { 'value' : 1, 'required' : 0,'type' : "int"  },
        'logname'     : { 'value' : 'CLDTest', 'required' : 0,'type' : "str"  },
        'monitorfile' : { 'value' : "mdsmon.txt", 'required' : 0,'type' : "str"  },
        'mntpnt'      : { 'value' : "/mnt/session", 'required' : 0,'type' : "str" },
        'scriptname'  : { 'value' : ( inspect.stack()[0][1] ), 'required' : 0,'type' : "str" },
        'testdir'     : { 'value' : None, 'required' : 0,'type' : "str"  },
        'testcases'   : { 'value' : "all", 'required' : 0,'type' : "str"  },
        'testname'    : { 'value' : "CLDTest", 'required' : 1,'type' : "str" },
    }
    rc = 0
    testinfo = MGTest.MGTest(opts)
    if testinfo.error:
        if hasattr(testinfo,'testlog'):
            testinfo.testlog.error(testinfo.error)
        else:
            print "TestSetup:SETUPERROR:",testinfo.error
        return -1
    cldopts = {}
    cldopts['ip'] = testinfo.settings.get('gridip')
    cldopts['username'] = "root"
    cldopts['password'] = "******"
    cld = MGCLD(cldopts,testinfo)
    if testinfo.error: return -1
    if testinfo.settings['testcases'] == 'all':
        setattr(testinfo,"testcases",testcases)
    else:
        setattr(testinfo,"testcases",[])
        tests = testinfo.settings['testcases'].split(",")
        for test in tests:
            if test: testinfo.settings['testcases'].append(test)
    testlog = logging.getLogger('mgtest')
    testlog.debug("returning %d" % rc)
    return rc
                
            
def MainTest():
    rc = TestSetup()
    if rc == -1: return
    opts = {}
    for test in testinfo.testcases:
        opts['testname'] = str(test)
        opts['title'] = testinfo.testcases[test]['title'] 
        testinfo.StartSubTest(opts)
        testinfo.testcases[test]['func']()
        testinfo.EndSubTest()
    testinfo.EndTest()
    return 0
        
    


if __name__ == '__main__':
    MainTest()   
    exit(0) 
        
        
        
        
    

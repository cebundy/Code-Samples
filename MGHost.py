#!/usr/bin/env python
import os
import sys
import string
import re
import platform
import subprocess
import inspect
import netifaces
import logging
from netifaces import AF_INET
if os.name == "nt":
    import win32wnet, win32api, win32netcon

class MGHost(object):
    '''MG Host class:  creates a host object that includes the local host configuration.
    '''
    def __init__(self,opts):
        if hasattr(opts,'testlog'):
            self.testlog = opts.testlog
        else:
            logging.basicConfig(format="%(asctime)s:%(name)s:%(levelname)s:%(module)s:%(funcName)s:%(lineno)d: %(message)s",level=logging.INFO)
            logger = logging.getLogger('mgtest')
            logger.setLevel(logging.DEBUG)
            self.testlog =  logger
        self.GetHostInfo()

    def GetHostInfo(self):
        'Get platform information from the localhost.'
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        os.system("ntpdate -u 10.4.2.8")
        self.platform = platform.platform()
        self.hostname = platform.node()
        self.osplat = platform.system()
        self.arch = platform.processor()
        self.fsd = self.GetFSD()
        self.GetNICInfo()


    def GetNICInfo(self):
        'get nic info  - should be os agnositic'
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("Started")
        nics = netifaces.interfaces()
        self.nics = {}
        for item in nics:
            if item == "lo":
                continue
#            print "processing ", item
            self.nics[item] = {}
            niccfg = netifaces.ifaddresses(item)
#            print thisfunc + ": niccfg: ", niccfg
            if niccfg.has_key(AF_INET):
                ifinfo = niccfg.get(AF_INET)
#                print thisfunc + ": af_inet info: ", ifinfo
                addr = ifinfo[0].get('addr')
#                print thisfunc + ": addr" + addr
                self.nics[item]['ip'] = addr
                self.nics[item]['mask'] = ifinfo[0].get('netmask')
            else:
                self.nics[item]['ip'] = "None"


    def GetFSD(self):
        ''' Gets the FSD version from the local host.  Supports
        Linux, Mac OS X, and Windows (assumes FSD is installed in %ProgramFiles(x86)%)
        '''
        thisfunc = inspect.stack()[0][3]
        fsd = {}
        command = None
        shellsetting = True
        print thisfunc,"os platform:", self.osplat
        if self.osplat == 'Linux':
            command = 'rpm -qa|grep FSD'
            # first we get the version for the rpm 
            p = subprocess.Popen(command, shell=shellsetting, stdout=subprocess.PIPE)
            output,err = p.communicate()
            lines = output.splitlines()
            if len(lines) == 0:
                fsd['version'] = "Not Installed"
                return fsd
            else:
                fsd['version'] = lines[0]
            command = 'sysctl -a|grep omfs'
        elif self.osplat == 'Darwin':
            command = 'sysctl -a|grep omfs'
        elif self.osplat == 'Windows':
        # Might need to do a check here to ensure that the FSD is installed here
            epath = os.environ.get('ProgramFiles(x86)') + "\Omneon\Omneon MediaGrid\omservice.exe"
            if os.path.lexists(epath) == False:
                epath = os.environ.get('ProgramFiles') + "\Omneon\Omneon MediaGrid\omservice.exe"
                if os.path.lexists(epath) == False:
                    return "Not Installed"
            command = "wmic product"
            # Windows doesn't mind the spaces in the path name if we open the subprocess with no shell
            shellsetting = False
        else:
            return "Unknown"
        print thisfunc,"command:",command
        p = subprocess.Popen(command, shell=shellsetting, stdout=subprocess.PIPE)
        output,err = p.communicate()
        lines = output.splitlines()
        if err != None:
            self.testlog.error(err)
            return 0
        if self.osplat == "Windows":
            for line in lines:
                m = re.search('OmneonWinFSD64\-(.*).msi',line)
                if m:
                    fsd['version'] = m.groups()[0] 
                    break
#             if len(lines) != 3:
#                 error = "Bad output for command: %s\nOutput: %s" % (command,output)
#                 self.testlog.error(error)
#             temp = lines[1].split('OmRdrService ')
#             temp2 = lines[2].split('Build stamp: ')
#             fsd['version'] = temp[1] + " " + temp2[1]
        elif self.osplat == "Darwin":
            for line in lines:
                parts = line.split('debug.omfs_')
                key, value = parts[1].split(': ')
                fsd[key] = value
        elif self.osplat == "Linux":
            for line in lines:
                parts = line.split('omfs_')
                key, value = parts[1].split(' = ')
                fsd[key] = value
        return fsd

        
    def MountShare(self,testinfo,opts):
        'Mount the MG filesystem'
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug(" started")
        rc = -1
        if self.osplat == 'Windows':
            rc = self.WinMapDrive(testinfo,opts)
        elif self.osplat == "Darwin":
            rc = self.OSXMountShare(testinfo,opts)
        elif self.osplat == "Linux":
            rc = self.LXMountShare(testinfo,opts)
        else:
            testinfo.error = "MountShare: Platform not supported (%s)" % self.osplat 
        return rc
    
    def UnMountShare(self,testinfo,opts):
        'Unmount the MG filesystem, OS agnostic method'
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        rc = -1
        if self.osplat == 'Windows':
            rc = self.WinDeleteDriveMapping(testinfo,opts)
        elif self.osplat == "Darwin":
            rc = self.OSXUnMountShare(testinfo,opts)
        elif self.osplat == "Linux":
            rc = self.LXUnMountShare(testinfo,opts)
        else:
            testinfo.error = "MountShare: Platform not supported (%s)" % self.osplat 
        return rc
        
        
    def LXUnMountShare(self,testinfo,opts):
        'unmount a share on a Linux host'
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        if "mntpnt" not in opts:
            self.testlog.error("'mntpnt' is required in opts")
            return -1
        command = "umount " + opts['mntpnt']
        output,err = self.RunCommand(command)
        if err:
            msg = "Unable to unmount " + opts['mntpnt'] + ":\nCommand: " + command \
              + "\nError: " + err 
            self.testlog.warn(msg)
            return -1
        print thisfunc + ": ", output
        return 0

    def OSXUnMountShare(self,testinfo,opts):
        'mount a share on a OS X host'
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        if "mntpnt" not in opts:
            self.testlog.error("'mntpnt' is required in opts")
            return -1
        command = "umount  " + opts['mntpnt']
        output,err = self.RunCommand(command)
        if err:
            msg = "Unable to unmount " + opts['mntpnt'] + ":\nCommand: " + command \
              + "\nError: " + err 
            self.testlog.warn(msg)
            return -1
        print thisfunc + ": ", output
        return 0

    def WinDeleteDriveMapping(self,testinfo,opts):
        'delete the MG drive mapping on a windows host.'
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        if "mntpnt" not in opts:
            self.testlog.error("'mntpnt' is required in opts")
            return -1
        command = "net use /d " + opts['mntpnt']
        output,err = self.RunCommand(command)
        if err:
            msg = "Unable to unmap " + opts['mntpnt'] + ":\nCommand: " + command \
              + "\nError: " + err 
            self.testlog.warn(msg)
            return -1
        print thisfunc + ": ", output
        return 0
    
    
    def LXMountShare(self,testinfo,opts):
        'mount a share on a local Linux host'
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        print "opts: ", opts
        print "opts host: ",opts['host']
        error = None
        fstype = None
        if 'type' in opts:
            fstype = opts['type']
        else:
            fstype = 'omfs'
            
        if fstype == "omfs":
            if 'passwd' not in opts: opts['passwd'] = 'usm'
            if 'user' not in opts: opts['user'] = 'omneon'
            if 'share' not in opts: opts['share'] = "testfs"
        else:
            if 'passwd' not in opts: error = "'passwd' is required in opts"
            if 'user' not in opts: error = "'user' is required in opts"
            if 'share' not in opts: error = "'share' is required in opts"
            if error:
                self.testlog.error(error)
                return -1
        if "mntpnt" not in opts:
            self.testlog.error("'mntpnt' is required in opts")
            return -1
        if not os.path.exists(opts['mntpnt']):
            try:
                self.testlog.info("Creating %s" % opts['mntpnt'])
                os.makedirs(opts['mntpnt'])
            except OSError, e:
                self.testlog.error("Unable to create mount point %s: %s" % \
                  (opts['mntpnt'],e))
                return -1
        command = 'mount -t %s ' % (fstype)
        if fstype == 'omfs':
            command = command + '/%s/%s %s -o username=%s,password=%s' % \
            (opts['host'], opts['share'], opts['mntpnt'], opts['user'], 
             opts['passwd'])
        else:
            command = command + '//%s/%s %s -o username=%s,password=%s' % \
            (opts['host'], opts['share'], opts['mntpnt'], opts['user'], 
             opts['passwd'])
        
        output,err = self.RunCommand(command)
        print thisfunc + ": output: ", output
        print thisfunc + ": err: ", err
        if err != '' and "already mounted" not in err:
            self.testlog.error('Unable to mount %s/%s on %s\nCommand: %s\nResult: %s' % \
            (opts['host'],opts['share'],opts['mntpnt'],command,err))
            return -1
        else:
            return 0
    


    
    
    def OSXMountShare(self,testinfo,opts):
        'mount a share on OSX host'
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        return 0    
        
    
    def RunCommand(self,command):
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        print thisfunc + "running command: " + command
#        output = ''
        output = []
        p = subprocess.Popen(command, shell=True, stderr=subprocess.PIPE)
        output,err = p.communicate()
#         print thisfunc + "output: ", output
#         print thisfunc + "err: ", err
        return output, err
                
#        while True:
#            out = p.stderr.readline(1)
#            print "out: ", out
#            if out == '' and p.poll() != None:
#                break
#            if out != '':
#                output = output + out
#                output.append(str(out))
#        print "output: ", output
#        return output
        
        
    def WinMapDrive(self,testinfo,opts):
        'map a MG filesystem on Windows'
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        
        drive = ""
        networkPath = '\\\\' + opts.get('host') + "\\" + opts.get('share')
        user = opts.get('user')
        password = opts.get('passwd')
        print networkPath
        if 'drive' not in opts:
            drives = self.WinGetFreeDriveLetter()
            drive = drives.pop(-1)
            if hasattr(self,'testlog'):
                self.testlog.debug("WinGetFreeDriveLetter returned %s" % drive)
            else:
                print thisfunc,"WinGetFreeDriveLetter returned %s",drive
        else:
            drive = opts['drive']
            if (os.path.exists(drive)):
                print drive, " %s Drive in use, trying to unmap..." % (drive)
                if 'force' in opts:
                    try:
                        win32wnet.WNetCancelConnection2(drive, 1, 1)
                        print drive, "successfully unmapped..."
                    except:
                        self.error = "Unmap failed on %s, This might not be a network drive..." % (drive)
                        return -1
                else:
                    self.error =  "%s is in use." % (drive)
                    return -1
#         else:
#             print drive, " drive is free..."
        if (os.path.exists(networkPath)):
            print networkPath, " is found..."
            print "Trying to map ", networkPath, " on to ", drive, " ....."
            try:
                win32wnet.WNetAddConnection2(win32netcon.RESOURCETYPE_DISK, drive, networkPath, None, user, password)
            except Exception, err:
                self.error = "Error mapping %s to %s as %s:%s: %s" % (drive, networkPath, user, password, str(err))
                if hasattr(self,'testlog'):
                    self.testlog.error(self.error)
                return -1
            print "Mapping successful "
            if hasattr(self,'testlog'):
                self.testlog.info("mapped %s to %s as %s:%s" % (drive, networkPath, user, password))
            return drive
        else:
            self.error =  "%s Network path unreachable..." % (networkPath)
            if hasattr(self,'testlog'):
                self.testlog.error(self.error)
            return -1

    def WinGetFreeDriveLetter(self):
        'returns the highest free drive letter'
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        drives=[]
        for c in string.lowercase:
            if os.path.isdir(c+':'):
                continue
            drives.append(c+':')
        return drives[:-1]
    
        
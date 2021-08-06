'''
Created on Jun 30, 2016

@author: cbundy
This performs file copy tests run on multiple threads.
Depending on test parameters, the test can also monitor and report
on cld system throttling activities and do file read performance tests.
'''
import os, threading, sys, inspect, logging, re
import time
import select
import subprocess
import platform
from subprocess import PIPE
from time import sleep, ctime
import Queue
import MGUtils
import MGTest
import MGMonitor
import MGLocalMonitor
import MGCluster
import MGHost


stop = 0
testinfo = None
testlog = None
tests = {}

def CreateDeleteDirs(opts):
    thisfunc = inspect.stack()[0][3]
    mythrd = threading.current_thread()
    tname = mythrd.name
    thisfunc = thisfunc + ':' + tname
    global stop, testlog, testinfo
    testlog.debug("started")

    if 'dircount' not in opts: opts['dircount'] = 100
    dirname = opts['mntpnt'] 
    dirname = CreateTestSubDir(dirname, tname)
    if dirname == -1: 
        testlog.info("%s: Unable to create directory: stopping" % mythrd)
        return -1
    command = "rm -fr " + dirname + "/*"
    testlog.debug("%s: created my test dir %s" % (tname,dirname))
    idx = 1
    error = None
    while not stop:
        indx = 1
        while indx <= opts['dircount']:
            subdirname = dirname + "/subdir" + str(idx)
#             testlog.debug("creating directory %s" % subdirname)
            try:
                os.makedirs(subdirname)
            except IOError, e:
                testlog.error("Unable to create directory %s: %s" % (subdirname,e))
                error = 1
                break
            idx += 1
            indx += 1
            del subdirname
        if error: break
#         testlog.debug("deleting directories in %s: command: %s" %\
#                       (dirname,command))
        os.system(command)
    testlog.debug("stopping")
    return 0      
    

def CreateFiles(opts):
    thisfunc = inspect.stack()[0][3]
    mythrd = threading.current_thread()
    tname = mythrd.name
    thisfunc = thisfunc + ':' + tname
    global stop, testlog, testinfo
    testlog.debug("started")
    print thisfunc,"opts",opts
    if 'fsize' not in opts: opts['fsize'] = 1 * 1024**2
    if 'fcount' not in opts: opts['fcount'] = 100
    dirname = opts['mntpnt'] 
    dirname = CreateTestSubDir(dirname, tname)
    if dirname == -1: 
        testlog.info("%s: Unable to create directory: stopping" % mythrd)
        return -1
    command = "rm -fr " + dirname + "/*"
    testlog.debug("%s: created my test dir %s" % (tname,dirname))
    mystr = "1" * 1024 + "\n"
    mysize = len(mystr)
    idx = 1
    error = None
    while not stop:
        indx = 1
        while indx <= opts['fcount']:
            filename = dirname + "/" + testinfo.settings['basename']  + \
            str(idx) + "." + testinfo.settings['fileext']
#             testlog.debug("opening %s" % filename)
            try: 
                fh = open(filename,"w")
            except IOError, e:
                testlog.error("Unable to open file %s: %s" % \
                  (filename,e))
                error = 1
                break
            byteswritten = 0
            while (byteswritten < opts['fsize']):
                try:
                    fh.write(mystr)
                except IOError, e:
                    testlog.error("Unable to write file %s: %s" % (filename,e))
                    error = 1
                    break
                byteswritten += mysize
            fh.close()
            if error: break
            idx += 1
            indx += 1
            del filename
        if error: break
#         testlog.debug("deleting files in %s" % dirname)
        os.system(command)
    testlog.debug("stopping")
    return 0

def ReadFilePerformanceTest(opts):
    thisfunc = inspect.stack()[0][3]
    mythrd = threading.current_thread()
    tname = mythrd.name
    thisfunc = thisfunc + ':' + tname
    global stop, testlog, testinfo
    testlog.debug("started %s" % tname)
    print thisfunc,"opts",opts
    if 'ptsize' not in opts: opts['ptsize'] = 2
    if 'fcount' not in opts: opts['fcount'] = 1
    if 'realdir'  in opts:
        dirname = opts['realdir']
    else: 
        dirname = opts['testdir'] 
        dirname = CreateTestSubDir(dirname, tname)
        if dirname == -1: 
            testlog.info("%s: Unable to create directory: stopping" % mythrd)
            return -1

    testlog.debug("%s: created my test dir %s" % (tname,dirname))
    # create a file on the grid
    if opts['ptsize'] < 1024:
        mystr = "1" * opts['ptsize']
    else:
        mystr = "1024"
    idx = 1
    rc = 0
    mysize = len(mystr)
    myfiles = []
    blocksize = 2 * 1024**2
    wcount = 0
    if opts['ptsize'] < blocksize:
        blocksize = opts['ptsize']
        wcount = 1
    else:
        wcount = opts['ptsize'] / blocksize
    testlog.debug("going into create file loop")
    error = 0
    while idx <= opts['fcount']:
        filename = dirname + "/" + "pt-"  + \
            str(idx) + "." + testinfo.settings['fileext']
        testlog.debug("creating file %s" % filename)
        if os.name == "nt":
            try: 
                fh = open(filename,"w")
            except IOError, e:
                testlog.error("Unable to open file %s: %s" % \
                  (filename,e))
                return -1
            byteswritten = 0
            while (byteswritten < opts['ptsize']):
                try:
                    fh.write(mystr)
                except IOError, e:
                    testlog.error("Unable to write file %s: %s" % (filename,e))
                    error = 1
                    break
                byteswritten += mysize
            fh.close()
            if error: break
                
        else:
            cmd = []
            cmd.append("dd")
            cmd.append(r"if=/dev/zero")
            cmd.append('of=' + filename)
            cmd.append("bs=" + str(blocksize))
            cmd.append("count=" + str(wcount))
    #         cmd = "dd if=/dev/zero of=%s bs=%d count=%d" %\
    #               (filename,blocksize,wcount)
            p = subprocess.Popen(cmd,stderr=subprocess.PIPE,stdout=subprocess.PIPE)
            while p.poll() is None:
                outp,serr = p.communicate()
                testlog.info("output: %s" % outp)
                testlog.debug("p.poll = 0")
                sleep(2)
            
        fstats = os.stat(filename)
        testlog.info("%s stats: " % str(fstats))
        myfiles.append(filename)
        idx += 1
    testlog.info("created file %s" % filename)
    if error: return -1
    
    # create a results file
    rfilename = testinfo.log['logdir'] + "/" + testinfo.host.hostname + \
       "-" + tname + MGUtils.GetLogTime()
    testlog.debug("creating results file: %s" % rfilename)
    try:
        rfile = open(rfilename,"w")
    except IOError, e:
        testlog.error("Unable to open file %s: %s" % \
          (rfilename,e))
        return -1
    
    # read files in a loop until global stop is set
#     results = {}
    testlog.debug("going into copy loop")
    error = 0
    highest = 0
    lowest = 0
    total = 0
    count = 0
    its = 0
    
    while not stop:
        for filename in myfiles:
            its += 1
            filename2 = filename + "-cp" + str(its) 
            if os.name == "nt":
                command = "copy %s %s" % (filename,filename2)
                command = command.replace("/","\\")
            else:
                command = "cp %s %s" % (filename,filename2)
            starttime = time.time()
            os.system(command)
            end = time.time()
            duration = float(end) - float(starttime)
            if duration > highest: highest = duration
            if not lowest or duration <= lowest: lowest = duration
            count += 1
            total += duration
            
            testlog.info("file: %s time: %.2f duration: %.2f" % (filename2,starttime,duration))
            tstamp = MGUtils.GetLogTime(starttime)
            rfile.write("%s,%.2f,%s\n" % (tstamp,duration,filename2))
            sleep(2)
        if error: break
    if error: rc = -1    
    if testinfo.settings['cleanup'] > 0:
        testlog.info("cleaning up by removing %s" % dirname)
        command = "rm -fr " + dirname 
        os.system(command)
    if total == 0 or count == 0:
        testlog.warning("no testperf iterations")
        rc = -1
    else:
        average = total / count
        msg = "%s: highest duration: %.2f" % (tname,highest)
        rfile.write(msg + "\n")
        testinfo.stats['msgs'].append(msg)
        msg = "%s: lowest duration: %.2f" % (tname,lowest)
        rfile.write(msg + "\n")
        testinfo.stats['msgs'].append(msg)
        msg = "%s: average duration: %.2f" % (tname,average)
        rfile.write(msg + "\n")
        testinfo.stats['msgs'].append(msg)
    rfile.close()
    return rc

    
    

def CreateTestSubDir(pdir,threadname):
    thisfunc = inspect.stack()[0][3]
    global testinfo, testlog
    testlog.debug("started")
    dirname = pdir + "/" + threadname + "-" + str(MGUtils.GetLogTime())
    try:
        os.makedirs(dirname, 0666)
    except IOError,e:
        testlog.error("Unable to create directory %s: %s" % (dirname,e))
        return -1
    testlog.debug("returning %s" % dirname)
    return dirname
    
def CreateTestDir(pdir):        
    thisfunc = inspect.stack()[0][3]
    global testinfo, testlog
    testlog.debug("started")
    scriptname = sys.argv[0]
    parts = scriptname.split(".")
    scriptname = parts[0]
#     print "scriptname",scriptname
    dirname = pdir + "/" + scriptname
#     print "creating parent test directory ",dirname
    if not os.path.exists(dirname):
        try:
            os.makedirs(dirname, 0666)
        except IOError,e:
            testlog.error("Unable to create directory %s: %s" % (dirname,e))
            return -1
    dirname = dirname + "/" + str(platform.node()) + "-" + str(MGUtils.GetLogTime())
#     print "creating test directory ",dirname
    os.makedirs(dirname, 0666)
    testlog.debug("returning %s" % dirname)
    return dirname

def ProcessQDepth(msg,mds):
    thisfunc = inspect.stack()[0][3]
    global testinfo, testlog
#     testlog.debug("started")
    m = re.search("qDepth (\d+)",msg)
    qdepth = None
    if m:
        qdepth = int(m.groups()[0])
#         testlog.debug("got qdepth for %s: %d" % (mds.hostname,qdepth))
    if qdepth == None: return
    mds.currentqdepth = qdepth
    if qdepth > mds.maxqdepth: 
        mds.maxqdepth = qdepth
        testlog
    if qdepth > 5000 and not mds.throttling:
        testlog.warning("%s: qdepth is %d throttling should be on" % \
                        mds.hostname,qdepth)
    elif qdepth < 5000 and mds.throttling:
        testlog.warning("%s: qdepth is %d throttling should be off" % \
                        mds.hostname,qdepth)
    return 0
        
        
        
        
    
def ProcessThrottling(msg,mds):
    thisfunc = inspect.stack()[0][3]
    global testinfo, testlog
    testlog.debug("started")
    if "ON" in msg:
        mds.throttling = 1
        mds.throttlingcount += 1
        testlog.info("%s: throttling is on" % mds.name)
    elif "OFF" in msg:
        testlog.info("%s: throttling is off" % mds.name)
        mds.throttling = 0
    return 0
    

def ReadMGMonitorQs():
    thisfunc = inspect.stack()[0][3]
    global testinfo, testlog, stop
    testlog.debug("started")
    while not stop:
        for mdsname in testinfo.cluster.mds:
            mds = testinfo.cluster.mds[mdsname]
            for filename in mds.monitors:
                monq = mds.monitors[filename].writeq
                while not monq.empty():
                    msg = mds.monitors[filename].writeq.get_nowait()
                    if "|E|" in msg: 
                        testlog.error("%s:%s: %s" %\
                                       (mdsname,filename,msg))
                    if 'qDepth' in msg:
                        ProcessQDepth(msg,mds)
                    if "thrott" in msg:
                        ProcessThrottling(msg,mds)
                        
    testlog.info("stopping")
    return 0


def SetupGrid():
    thisfunc = inspect.stack()[0][3]
    testlog.info("started")
    opts = {}
    opts['ip'] = testinfo.settings.get('gridip')
    opts['user'] = "root"
    opts['password'] = "omneon"
    testlog.debug("calling MGCluster")
    cluster = MGCluster.MGCluster(opts,testinfo)
    if testinfo.error:
        return -1
    testinfo.LogDict(cluster)
    setattr(testinfo,"cluster",cluster)
    if not testinfo.settings['gridmonitor']: 
        return 0
    opts['logdir'] = testinfo.log.get('logdir')
    opts['monitorfile'] = testinfo.settings.get('monitorfile')
    opts['user'] = 'root'
    opts['password'] = '******'
    opts['logger'] = testlog
    monfiles = ['mdscore','ssmd','mdscorestats']  
#         monfiles = ['mdscore']
    for mdsname in testinfo.cluster.mds:
        mds = testinfo.cluster.mds[mdsname]
        setattr(mds,"maxqdepth",0)
        setattr(mds,"currentqdepth",0)
        setattr(mds,"throttling",0)
        setattr(mds,"throttlingcount",0)
        
        opts['ip'] = mds.ip['public'][0]
        setattr(mds,'monitors',{})
        for thefile in monfiles:
            opts['filename'] = thefile
            opts['name'] = mdsname + "-" + thefile
            mds.monitors[thefile] = MGMonitor.MGMonitor(opts)
            if opts.has_key('error') and opts['error']:
                testinfo.error = "%s: failed to setup Monitor for %s: %s" \
                                    % (thisfunc,mdsname,opts['error'])
                return -1
            if thefile == "mdscore":
                mds.monitors[thefile].ReportlistAdd("qDepth")
                mds.monitors[thefile].ReportlistAdd("toggled")
                
    
    readmon = threading.Thread(target=ReadMGMonitorQs,name="readmonitorqs")
    readmon.start()
    setattr(testinfo,"readmonqs",readmon) 
    return 0

def SetupHost():
    thisfunc = inspect.stack()[0][3]
    global testinfo, testlog
    testlog.info("creating %d session mounts" %\
                  int(testinfo.settings['sessions']))
    mntopts = {}
#         mntopts['host'] = testinfo.cluster.clustername
    mntopts['host'] = testinfo.settings['gridip']
    mntopts['mntpnt'] = testinfo.settings['mntpnt']
    mntopts['share'] = "testfs"
    scount = 0
    setattr(testinfo,"mntpnts",[])
    sessions = int(testinfo.settings['sessions'])
    print "sessions: ",testinfo.settings['sessions']
    while scount < sessions:
        scount += 1
        mntpnt = "/mnt/session" + str(scount)
        testlog.info("mounting %s" % mntpnt)
        mntopts['mntpnt'] = mntpnt
        rc = testinfo.host.MountShare(testinfo, mntopts)
        if rc == -1:
            testlog.debug("mount error - returning -1") 
            return -1
        if os.name == 'nt':
            testinfo.mntpnts.append(rc)
        else:
            testinfo.mntpnts.append(mntpnt)
    tdir = CreateTestDir(testinfo.mntpnts[0])
    if tdir == -1: return -1
    tdir = tdir.replace(testinfo.mntpnts[0],"")
    testlog.debug("tdir: %s" % tdir)   
    testinfo.testdir = tdir
    testlog.debug("testdir: %s" % testinfo.testdir)
    if os.name != "nt":
        opts = {}
        opts['logdir'] = testinfo.log.get('logdir')
        if os.name != "nt":
            opts['filename'] = "C:\PROGRAM~2\Omneon\OMNEON~1\Log\ommrx.log"
        else:   
            opts['filename'] = "/var/log/messages"
        if testinfo.settings['monitorfile'] != None:
            opts['monitorfile'] = testinfo.settings['monitorfile']
        # start the host log monitor
        testlog.info("starting host monitor")
        hostmon = MGLocalMonitor.MGLocalMonitor(opts)
        setattr(testinfo,"hostmonitor",hostmon)
    
    return 0


    
def TestSetup(testopts):
    '''Setup test environment and variables'''
    thisfunc = inspect.stack()[0][3]
    global testinfo
    global testlog
    
    opts = {
        'basename'    : { 'value' : "cfiles", 'required' : 0,'type' : "str"},
        'blocksize'   : { 'value' : (2 * 1024**2), 'required' : 0,'type' : "str"  },
        'cleanup'     : { 'value' : 0, 'required' : 0,'type' : "int"  },
        'debug'       : { 'value' : 1, 'required' : 0,'type' : "int" },
        'dircount'    : { 'value' : 500, 'required' : 0,'type' : "int"  },
        'duration'    : { 'value' : '8H', 'required' : 0,'type' : "str" },
        'fileext'     : { 'value' : "data", 'required' : 0,'type' : "str"  },
        'fsize'       : { 'value' : 1024, 'required' : 0,'type' : "str"  },
        'fcount'      : { 'value' : 50, 'required' : 0,'type' : "int"  },
        'gridmonitor' : { 'value' : 1, 'required' : 0,'type' : "int" },
        'gridip'      : { 'value' : None, 'required' : 1,'type' : "str" },
        'interactive' : { 'value' : 1, 'required' : 0,'type' : "int"  },
        'logname'     : { 'value' : 'DirsAndFiles', 'required' : 0,'type' : "str"  },
        'monitorfile' : { 'value' : "mdsmon.txt", 'required' : 0,'type' : "str"  },
        'mntpnt'      : { 'value' : "/mnt/session", 'required' : 0,'type' : "str" },
        'ptsize'      : { 'value' : 2, 'required' : 0,'type' : "str" },
        'perftest'    : { 'value' : 1, 'required' : 0,'type' : "int"  },
        'realdir'     : { 'value' : None, 'required' : 0,'type' : "str"  },
        'scriptname'  : { 'value' : ( inspect.stack()[0][1] ), 'required' : 0,'type' : "str" },
        'sessions'    : { 'value' : 10, 'required' : 0,'type' : "int"  },
        'tcount'      : { 'value' : 200, 'required' : 0,'type' : "int"  },
        'tests'       : { 'value' : 1, 'required' : 0,'type' : "int"  },
        'testdir'     : { 'value' : None, 'required' : 0,'type' : "str"  },
        'testname'    : { 'value' : "CpTest", 'required' : 1,'type' : "str" },
    }
    for item in testopts:
        opts[item] = {}
        opts[item]['value'] = testopts[item]
    global testinfo, tests, testlog
    rc = 0
    testinfo = MGTest.MGTest(opts)
    if testinfo.error:
        if hasattr(testinfo,'testlog'):
            testinfo.testlog.error(testinfo.error)
            rc = -1
        else:
            print thisfunc,"SETUPERROR:",testinfo.error
            rc = -1
        return rc
    testlog = logging.getLogger('mgtest')
    testinfo.settings['fsize'] = MGUtils.CalcBytes(testinfo.settings['fsize'])
    testinfo.settings['ptsize'] = MGUtils.CalcBytes(testinfo.settings['ptsize'])
    testlog.info("fsize: %d" % testinfo.settings['fsize'])
    testlog.info("ptsize: %d" % testinfo.settings['ptsize'])
    if testinfo.settings['tests'] == 0:
        testinfo.settings['sessions'] = 1

    while True: # not a real loop
        if testinfo.stats['errorcount'] > 0:
            rc = -1
            break
        testinfo.settings['duration'] = \
          MGUtils.CalcSeconds(testinfo.settings['duration'])
        testlog.debug("duration: %s" % str(testinfo.settings['duration']))  
        testinfo.settings['fsize'] = \
          MGUtils.CalcBytes(testinfo.settings['fsize'])
        logging.debug("calling SetupHost")
        rc = SetupHost()
        if rc:
            testlog.debug("error during SetupHost - returning %d" % rc)
            if testinfo.error: testlog.error(testinfo.error)
        testlog.info("mntpnts = %s" % str(testinfo.mntpnts))
        break
    tests['dirs'] = CreateDeleteDirs
    tests['files'] = CreateFiles
    print thisfunc,"tests",tests
    testlog.debug("returning %d" % rc)
#     return -1 # TAKE THIS OUT!!!!
    return rc

def StartThreads():
    thisfunc = inspect.stack()[0][3]
    global testinfo, testlog, tests
    if testinfo.settings['tests'] != 0:
        rc = StartWorkerThreads()
        
    testlog.debug("started")
    if testinfo.settings["perftest"] > 0:
        testlog.info("starting perf test thread")
        tname = 'perftest'
        topts = {}
        if testinfo.settings['realdir'] != None:
            topts['realdir'] = testinfo.settings['realdir']
        topts['testdir'] = testinfo.mntpnts[0] + testinfo.testdir
        topts['ptsize'] = testinfo.settings['ptsize']
        topts['fcount'] = 1
        setattr(testinfo,"perftest",None)
        testinfo.perftest = threading.Thread(target=ReadFilePerformanceTest,name=tname,args=(topts,))
        testinfo.perftest.start()
    testlog.debug("returning 0")
    return 0

def StartWorkerThreads():
    thisfunc = inspect.stack()[0][3]
    global stop, testinfo, testlog
    testlog.debug("started")
    mytcount = 0
    tcount = int(testinfo.settings['tcount'])
    if tcount == 0: return 0
    testlog.debug("opening %d threads" % tcount)
    setattr(testinfo,"workerthrds",[])
    opts = {}
    opts['fcount'] = testinfo.settings['fcount']
    opts['dircount'] = testinfo.settings['dircount']
    opts['fsize'] = testinfo.settings['fsize']
    # open threads rotating between the mount points is a round-robin fashion
    maxindx = len(testinfo.mntpnts)
    indx = 0
    testlog.info("starting worker threads")
    while True:
        for item in tests:
            mytcount = mytcount + 1
            if indx == maxindx: indx = 0
            fname = str(tests[item])
            m = re.search("function (\w+) ",fname)
            if m:
                fname = m.groups()[0]
            else:
                fname = item
            tname = fname + '-' + str(mytcount)
            mntpnt = testinfo.mntpnts[indx]
            opts['mntpnt'] = mntpnt + testinfo.testdir
            testlog.debug("Creating thread %s with dir %s" % (tname,opts['mntpnt']))
            testlog.debug("tcount: %d  mytcount: %d" % (tcount,mytcount))
            myfunc = tests[item]
            thread1 = threading.Thread(target=myfunc,name=tname,args=(opts,))
            thread1.setDaemon(True)
            testinfo.workerthrds.append(thread1)
            thread1.start()
            if mytcount == tcount: break
            indx += 1
        if mytcount == tcount: break
    

def TestCleanup():
    thisfunc = inspect.stack()[0][3]
    global stop, testinfo, testlog
    testlog.debug("started")
    if testinfo.settings['cleanup'] != 0:
        testdir = testinfo.mntpnts[0] + '/' + testinfo.testdir
        testlog.info("Removing test directory: %s" % testinfo.testdir)
        command = "rm -fr %s" % testinfo.testdir
        os.system(command)
    for item in testinfo.mntpnts:
        if os.name == "nt":
            command = "net use %s \d" % item
        else:
            command = "umount %s" % item
        testlog.info("unmounting %s" % item)
        os.system(command)
    testlog.debug("returning 0")
    return 0
    
def StopTest():
    '''stop and joins the worker and other monitoring test threads via
    the global stop flag'''
    thisfunc = inspect.stack()[0][3]
    global stop, testinfo, testlog, testlog
    testlog.debug("started")
    stop = 1
    if hasattr(testinfo,"workerthrds"):
        sleep(30)
        for thrd in testinfo.workerthrds:
            testlog.debug("attempting to join %s" % thrd.name)
            thrd.join(1.5)
            if not thrd.is_alive():
                print thisfunc,"reaped thread ",thrd.name
    if testinfo.settings['gridmonitor'] == 1:
        testinfo.testlog.info("Stopping MG Monitors")
    
    if hasattr(testinfo,"perftest"):
        testlog.info("joining thread %s (join is blocking)" %\
                      testinfo.perftest.name)
        testinfo.perftest.join()
        
    if hasattr(testinfo,'cluster'):
        for mdsname in testinfo.cluster.mds:
            mds = testinfo.cluster.mds[mdsname]
            if hasattr(mds,"monitors"):
                for monfile in mds.monitors:
                    mds.monitors[monfile].StopMonitor()
                    
    if hasattr(testinfo,"readmonqs"):
        testinfo.testlog.info("%s: joining %s" %\
                               (thisfunc,testinfo.readmonqs.name))
        testinfo.readmonqs.join()
        
    if hasattr(testinfo,"hostmonitor"):
        testlog.info("Stopping Host Monitor")
        testinfo.hostmonitor.StopMonitor()
        
    TestCleanup()
    testinfo.EndTest()
#    testlog.debug("returning 0")
    return 0

def CheckChildren():
    '''Verify the running of the workerthreads'''
    thisfunc = inspect.stack()[0][3]
    global testinfo, testlog
    testlog.debug("started")
    threadcount = 0
    if testinfo.settings['tests'] != 0:
        for thrd in testinfo.workerthrds:
            if not thrd.is_alive():
                testlog.info("thread is dead: %s" % thrd.name)
                testinfo.workerthrds.remove(thrd)
            else:
                threadcount += 1
        if not threadcount:
            testlog.error("FATALFAIL: ALL THREADS HAVE DIED")
            testinfo.stats['result'] = 'FATALFAIL'
        elif threadcount < int(testinfo.settings['tcount']):
            remainingthreads = int(testinfo.settings['tcount']) - threadcount
            if not hasattr(testinfo,"remainingthreads") or \
               remainingthreads < testinfo.remainingthreads:
                testinfo.remainingthreads = remainingthreads
                testlog.error("only %d threads of %d are still running" %\
                              (threadcount,int(testinfo.settings['tcount'])))
        testlog.info("%d threads are running" % threadcount)
    if hasattr(testinfo,"perftest"):
        if not testinfo.perftest.is_alive():
            testlog.error("FATALFAIL: PERFTEST THREAD HAS DIED")
            testinfo.stats['result'] = 'FATALFAIL'
        else:
            testlog.info("perftest is running")
    
    testlog.debug("returning 0")
    return 0
         
     
def main():
    thisfunc = inspect.stack()[0][3]
    global stop, testinfo, testlog
    testopts = {}
    rc = TestSetup(testopts)
    if rc:
        if hasattr(testinfo,"cluster"):
            testlog.debug("error during TestSetup: calling StopTest")
            StopTest() 
            return 0
        if testlog:
            testlog.debug("error during TestSetup: returning 0")
        return 0
    testlog.info("Calling StartThreads")    
    StartThreads()
    
    testlog.debug("starting wait period")
    starttime = time.time()
    while (time.time() - starttime) < int(testinfo.settings['duration']):
        sleep(10)
        duration = time.time() - starttime
        remaining = int(testinfo.settings['duration']) - duration
        testlog.info("test duration: %d  time remaining: %d" % \
                         (duration,remaining))
        CheckChildren()
        if testinfo.stats['result'] == "FATALFAIL": break
    testlog.info("Calling StopTest")    
            
    StopTest()
#    testlog.debug("returning 0")
    return 0
   
    
    
if __name__ == '__main__':
    main()
    print "all done"
    sys.exit()
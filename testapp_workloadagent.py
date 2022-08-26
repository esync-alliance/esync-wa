#!/usr/bin/env python3

# Copyright Excelfore Corporation, - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.
# Its use or disclosure, in whole or in part, without
# written permission of Excelfore Corp. is prohibited.

import workloadagent
import sys
import os
import shutil
from optparse import OptionParser
from workloadagent import WorkloadAgent

def checkResult(functionName, retVal, success):
    print("[TEST::%s::] %s returned ==> [%s] " % ("PASSED" if success else "FAILED", functionName, retVal))

if __name__ == "__main__":

    print("WA: Running: %s" % ' '.join(sys.argv[0:]))
    parser = OptionParser(usage="usage: %prog [options]", version="%prog 1.0")
    parser.add_option("-k", "--cert", default='/data/sota/certs/rom-ua/', type='string',
                      action="store", dest="cert_dir", help="certificate directory", metavar="CERT")
    parser.add_option("-t", "--type", default='/ECU/ROM', type='string',
                      action="store", dest="node_type", help="handler type", metavar="TYPE")
    parser.add_option("-i", "--host", default='localhost', type='string',
                      action="store", dest="host", help="host (localhost)")
    parser.add_option("-p", "--port", default=9133, type='int',
                      action="store", dest="port", help="port (9133)")
    parser.add_option("-u", "--user", type='string', action="store",
                      dest="ssh_user", help="ssh user name ", metavar="USER")
    parser.add_option("-w", "--pass", type='string', action="store",
                      dest="ssh_pw", help="ssh password ", metavar="PASS")
    parser.add_option("-s", "--sshport", default=22, type='int',
                      action="store", dest="sshport", help="port (22)")
    parser.add_option("-a", "--cap", default='A:3;B:3;C:100', type='string', action="store",
                      help="delta capability ", metavar=" CAP")
    parser.add_option("-c", "--temp", default='/tmp/esync', type='string', action="store",
                      dest="cache", help="cache directory ", metavar="TEMP")
    parser.add_option("-b", "--back", default='/data/sota/esync', type='string', action="store",
                      dest="backup_dir", help="backup  directory ", metavar="BKUP")
    parser.add_option('-l', '--load', default=False, action='store_true', dest="ready_download",
                      help="enable  DOWNLOAD_CONSENT to ready-download")
    parser.add_option('-D', '--delta', default=False, action='store_true', dest="disable_delta",
                      help="disable delta")
    parser.add_option("-W", "--wa_dir", default='/usr/share/wa/', type='string',
                      action="store", dest="wa_dir", help="workload agent install dir", metavar="WA")
    parser.add_option("-j", "--json", default='/usr/share/wa/wa-schema.json', type='string',
                      action="store", dest="json", help="workload agent schema file", metavar="JSON")
    parser.add_option("-m", "--mtimeout", default=5, type='int',
                      action="store", dest="mtimeout", help="mtimeout (default=5 minutes)")
    parser.add_option('-d', '--debug', default=3, action='store', type='int',
                      help="debug level(3), 1=ERROR, 2=WARN, 3=INFO, 4=DEBUG", metavar="LVL")
    parser.add_option("-1", "--arg1", default='CONTAINER-UPDATE-DEMO', type='string',
                      action="store", dest="arg1", help="for test only packageName")
    parser.add_option("-2", "--arg2", default='1.2.0', type='string',
                      action="store", dest="arg2", help="for test only packageVersion")  
    parser.add_option("-3", "--arg3", default='/tmp/wa/CONTAINER-UPDATE-DEMO-1.2.0.x', type='string',
                      action="store", dest="arg3", help="for test only packageFile")
    parser.add_option("-4", "--arg4", default='/usr/share/workloadagent/', type='string',
                      action="store", dest="arg4", help="for test only localPath")
    parser.add_option("-5", "--arg5", default='CONTAINER-UPDATE-DEMO-1.2.0.x', type='string',
                      action="store", dest="arg5", help="for test only packageFilename")  
    (options, args) = parser.parse_args()

    host_p = 'tcp://' + options.host + ':' + str(options.port)
    sample_ua = WorkloadAgent(cert_dir=options.cert_dir,
                         ua_nodeType=options.node_type,
                         host_port=host_p,
                         delta_cap=options.cap,
                         enable_delta=(options.disable_delta is False),
                         debug=options.debug,
                         backup_dir = options.backup_dir,
                         cache_dir = options.cache,
                         ready_download=options.ready_download)

    sample_ua.ssh_host = options.host
    sample_ua.ssh_user = options.ssh_user
    sample_ua.ssh_pw = options.ssh_pw
    sample_ua.ssh_port = options.sshport
    sample_ua.cache = options.cache
    sample_ua.backup = options.backup_dir
    sample_ua.instdir    = options.wa_dir
    sample_ua.schema    = options.json
    sample_ua.mtimeout    = options.mtimeout
    # for unit test only, arguments to pass to UA callback
    packageName=options.arg1
    packageVersion=options.arg2
    packageFile=options.arg3
    localPath=options.arg4
    packageFilename=options.arg5


    # re-create target directories
    if not os.path.exists(sample_ua.instdir):
        os.makedirs(sample_ua.instdir)
    
    if os.path.exists(sample_ua.cache):
        shutil.rmtree(sample_ua.cache)
    os.makedirs(sample_ua.cache)

    if os.path.exists(sample_ua.backup):
        shutil.rmtree(sample_ua.backup)
    os.makedirs(sample_ua.backup)
    

    sample_ua.do_init()
    checkResult("do_init", 0, True)

    retVal = sample_ua.do_confirm_download(packageName, packageVersion)
    checkResult("do_confirm_download", retVal, retVal=="DOWNLOAD_CONSENT")
    
    retVal = sample_ua.do_transfer_file(packageName, packageVersion, packageFile)
    checkResult("do_transfer_file", retVal[-1], 
        retVal[0] == 0 and os.path.exists(sample_ua.backup + os.sep + packageFilename))
    
    retVal = sample_ua.do_prepare_install(packageName, packageVersion, sample_ua.backup + os.sep + packageFilename)
    checkResult("do_prepare_install", retVal[0], 
        retVal[0] == "INSTALL_READY" and os.path.exists(sample_ua.cache + os.sep + packageFilename))
    
    retVal = sample_ua.do_pre_install("")
    checkResult("do_pre_install", retVal, retVal == "INSTALL_IN_PROGRESS")
    
    retVal = sample_ua.do_install(packageVersion, sample_ua.cache + os.sep + packageFilename)
    checkResult("do_install", retVal, retVal == "INSTALL_COMPLETED")

    sample_ua.do_post_install(packageName)
    checkResult("do_init", 0, True)

    retVal = sample_ua.do_set_version(packageName, packageVersion)
    checkResult("do_set_version", retVal, retVal == 0)

    retVal = sample_ua.do_get_version(packageName)
    checkResult("do_get_version", retVal[-1], retVal[-1] == packageVersion)


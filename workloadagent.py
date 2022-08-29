#!/usr/bin/env python3

# Copyright Excelfore Corporation, - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.
# Its use or disclosure, in whole or in part, without
# written permission of Excelfore Corp. is prohibited.

import os
import subprocess
import shutil
import sys
from optparse import OptionParser
from pylibua.esyncua import eSyncUA
import json
import jsonschema
from jsonschema import validate
import subprocess
import sys
import zipfile
import glob
import yaml
import time
import xml.etree.ElementTree as ET


# Constants and definitions
VERIFY_WAIT_DURATION=5
KEY_DEPLOYMENT_NAME="deploymentName"
KEY_CONTAINER="container"
KEY_IMAGE_NAME="imageName"
KEY_IMAGETAG="imageTag"
KEY_CONF_FILENAME="confFilename"
KEY_HASH="hash"

CHECK_RESULT = ('RET_SUCCESS', # Update deployment successful
                'RET_INPROGRESS', # Pod status is not yet verified
                'RET_TIMEOUT', # Timeout occurred before pod status is verified
                'RET_DIGEST',  # Invalid digest in json file
                'RET_TAG',     # Invalid image tag in yaml file
                'RET_ERR')     # General error

# Global config
retry_wait_run_kubectl_cmd=10

def printlog(message):
    print(message)
    sys.stdout.flush()

def run_kubectl_cmd(command):
    printlog("WA: ### " + command)
    p = subprocess.run(command, shell=True, stdout=subprocess.PIPE, universal_newlines=True)
    return p.stdout.strip()

def wait_run_kubectl_cmd(command):
    # kubectl calls may take a while to reflect the expected result, do a few retries
    for i in range(1,retry_wait_run_kubectl_cmd+1):
        result = run_kubectl_cmd(command)
        if result:
            break
        else:
            time.sleep(1)
            continue
    return result

def check_container_update(deploymentName, imageTag, waitForRunning, imageDigest):
    result = 'RET_SUCCESS'
    cmd_current_rs_name="kubectl describe deployment %s |grep \"^NewReplicaSet\"|awk '{print $2}'" % (deploymentName)

    current_rs_name = wait_run_kubectl_cmd(cmd_current_rs_name)
    if not current_rs_name:
        result = 'RET_ERR'
    else:
        cmd_current_pod_hash_label="kubectl get rs %s -o jsonpath=\"{.metadata.labels.pod-template-hash}\"" % (current_rs_name)
        current_pod_hash_label = wait_run_kubectl_cmd(cmd_current_pod_hash_label)

        cmd_current_pod_names="kubectl get pods -l pod-template-hash=%s --show-labels | tail -n +2 | awk '{print $1}'" % (current_pod_hash_label)
        current_pod_names =wait_run_kubectl_cmd(cmd_current_pod_names)
        if not current_pod_names:
            result = 'RET_ERR'
        else:
            cmd_current_pod_image="kubectl get pods/%s -o jsonpath=\"{..containers[*].image}\"" % (current_pod_names)
            current_pod_image = wait_run_kubectl_cmd(cmd_current_pod_image)

            # Verify Pod Status
            cmd_current_pod_status="kubectl get -o template pod/%s --template={{.status.phase}}" % (current_pod_names)
            current_pod_status = wait_run_kubectl_cmd(cmd_current_pod_status)
            if current_pod_status != "Running":
                printlog("WA: Pod is not yet running")
                if waitForRunning:
                    result = 'RET_TIMEOUT'
                else:
                    result = 'RET_INPROGRESS'
                return result
            else:
                printlog("WA: Pod is Running")

            # Verify Image Tag
            currentTag = current_pod_image.rsplit(':', 2)[-1]
            if imageTag != currentTag:
                printlog("WA: Mismatch expected=%s current=%s" % (imageTag, currentTag))
                result = 'RET_TAG'
            else:
                printlog("WA: Tag verified.")

            # Verify Image ID/Digest
            cmd_current_pod_imageId="kubectl get pods %s  -o jsonpath=\"{..imageID}\"" % (current_pod_names)
            current_pod_imageId = wait_run_kubectl_cmd(cmd_current_pod_imageId)
            currentTagId = current_pod_imageId.rsplit(':', 3)[-1]
            if imageDigest != "" and imageDigest != currentTagId:
                printlog("WA: Image Digest mismatch hash=%s current=%s" % (imageDigest, currentTagId))
                result = 'RET_DIGEST'
            else:
                printlog("WA: Image Digest verified/skipped.")
    return result

def wait_check_container_update(deploymentName, imageTag, imageDigest, timeout):
    result = 'RET_ERR'
    elapsed_sec=0;
    t0 = time.time()

    # If timeout is set, wait for pod running until timeout elapsed
    # otherwise, try once, then return INSTALL_IN_PROGRESS
    if timeout == 0:
        verify_wait_flag = False
    else:
        verify_wait_flag = True

    while(elapsed_sec <= timeout*60):
        result = check_container_update(deploymentName, imageTag, verify_wait_flag, imageDigest)
        elapsed_sec = time.time() - t0
        if result == 'RET_SUCCESS' or result == 'RET_INPROGRESS':
            break
        if result == 'RET_TIMEOUT':
            time.sleep(VERIFY_WAIT_DURATION)
            printlog("WA: Pod is not yet ready, Retry...")
            continue
        else:
            printlog("WA: failed to update %s " % result)
            break
    return result

def findkeys(node, kv):
    if isinstance(node, list):
        for i in node:
            for x in findkeys(i, kv):
               yield x
    elif isinstance(node, dict):
        if kv in node:
            yield node[kv]
        for j in node.values():
            for x in findkeys(j, kv):
                yield x

def get_yaml_config_details(yamlFile):
    with open(yamlFile, "r") as read_file:
        try:
            yamlData = yaml.safe_load(read_file)
            read_file.close()
        except yaml.YAMLError as exc:
            print(exc)

    retList = list(findkeys(yamlData, KEY_DEPLOYMENT_NAME)) + list(findkeys(yamlData, KEY_IMAGETAG))

    return (retList)

def jsonValidate(workloadList, schemaFile):
    with open(schemaFile, "r") as read_file:
        workloadSchema = json.load(read_file)
    read_file.close()

    try:
        validate(instance=workloadList, schema=workloadSchema)
    except jsonschema.exceptions.ValidationError as err:
        return False
    return True

def jsonRun(workloadList, targetdir, timeout):
    retVal = 'RET_ERR'
    failed_items = 0
    pended_items = 0
    for item in workloadList:
        if KEY_HASH in item:
            hash=item[KEY_HASH]
        else:
            hash=""
        if KEY_DEPLOYMENT_NAME in item:
            cmd="kubectl set image deployment/%s %s=%s:%s" % (item[KEY_DEPLOYMENT_NAME],
                    item[KEY_CONTAINER],item[KEY_IMAGE_NAME],item[KEY_IMAGETAG])
            run_kubectl_cmd(cmd)
            retVal = wait_check_container_update(item[KEY_DEPLOYMENT_NAME], item[KEY_IMAGETAG], hash, timeout)

        elif KEY_CONF_FILENAME in item:
            cmd="kubectl apply -f %s/%s " % (targetdir, item[KEY_CONF_FILENAME])
            run_kubectl_cmd(cmd)

            retList = get_yaml_config_details(targetdir + os.sep + item[KEY_CONF_FILENAME])

            if len(retList) > 1:
                retVal = wait_check_container_update(retList[0], retList[1], hash, timeout)
            else:
                printlog("WA: No imageTag in annotation, skip")
                retVal = 'RET_SUCCESS'
        else:
            printlog("WA: Item is invalid")
            retVal = 'RET_ERR'

        # Check update result and count accordingly
        if retVal == 'RET_INPROGRESS':
            pended_items+=1
        elif retVal != 'RET_SUCCESS':
            failed_items+=1

        # Check if we need to timeout
        if retVal == 'RET_TIMEOUT':
            printlog("WA: Update timed out")
            break

    if failed_items == 0 and pended_items == 0:
        status = 'INSTALL_COMPLETED'
    elif failed_items == 0 and pended_items > 0:
        status = 'INSTALL_IN_PROGRESS'
    else:
        status = 'INSTALL_FAILED'
    return status

def jsonLoad(jsonFilename, install_target, schemaFile, timeout):
    update_status='INSTALL_FAILED'
    with open(jsonFilename, "r") as read_file:
        jsonData = json.load(read_file)
        read_file.close()

        if jsonValidate(jsonData, schemaFile):
            update_status = jsonRun(jsonData, install_target, timeout)
        else:
            printlog("WA: workload list is not valid")

    printlog("WA: Update status=%s" % (update_status))
    return update_status

def manifestLoad(manifestFile):
    xmltree = ET.parse(manifestFile)
    xmlroot = xmltree.getroot()
    for child in xmlroot.iter('payload'):
        payload = child.text
    return payload

class WorkloadAgent(eSyncUA):
    """ Workload Agent """

    def do_init(self):
        printlog("WA: do_init")
        pass

    def do_confirm_download(self, pkgName, version):
        printlog("WA: do_confirm_download %s:%s" % (pkgName, version))
        return 'DOWNLOAD_CONSENT'

    def do_pre_install(self, downloadFileStr):
        if not downloadFileStr:
            printlog("WA: do_pre_install %s " % (downloadFileStr))
        else:
            printlog("WA: do_pre_install ")
        return 'INSTALL_IN_PROGRESS'

    def do_install(self, version, packageFile):
        update_status = 'INSTALL_FAILED'
        printlog("WA: do_install version: %s with %s" % (version, packageFile))
        filename = self.cache + os.sep + os.path.basename(packageFile)
        install_target = self.instdir + os.sep + os.path.basename(packageFile)

        if not os.path.exists(install_target):
            os.makedirs(install_target)

        with zipfile.ZipFile(filename, 'r') as zip_ref:
            zip_ref.extractall(install_target)

        payloadFile = manifestLoad(install_target + os.sep + "manifest.xml")
        payloadPath = install_target + os.sep + payloadFile
        if os.path.exists(payloadPath):
            with zipfile.ZipFile(payloadPath, 'r') as zip_payload:
                zip_payload.extractall(install_target)

            for name in glob.glob(install_target + os.sep + "*.json"):
                update_status = jsonLoad(name, install_target, self.schema, self.mtimeout)

        return update_status

    def do_post_install(self, packageName):
        printlog("WA: do_post_install %s" % (packageName))
        return

    def do_get_version(self, packageName):
        printlog("WA: do_get_version %s " % (packageName))
        return eSyncUA.do_get_version(self, packageName)

    def do_set_version(self, packageName, ver):
        printlog("WA: do_set_version %s %s" % (packageName, ver))
        eSyncUA.do_set_version(self, packageName, ver)
        return 0

    def do_prepare_install(self, packageName, version, packageFile):
        printlog("WA: do_prepare_install %s:%s:%s" %
              (packageName, version, packageFile))
        try:
            newFile = self.cache + os.sep + os.path.basename(packageFile)
            try:
                os.remove(newFile)
            except:
                pass
            shutil.copy(packageFile, newFile)
            printlog("WA: do_prepare_install returns %s " % newFile)
            return ['INSTALL_READY', newFile]
        except Exception as why:
            printlog("WA: copy error: <%s>" % (str(why)))
            return ['INSTALL_FAILED']

    def do_transfer_file(self, packageName, version, packageFile):
        printlog("WA: do_transfer_file : %s %s with %s" % (packageName, version, packageFile))
        if self.ssh_user is None:
            status = 0
        else:
            try:
                remote_path = self.ssh_user + '@' + self.ssh_host + ':' + packageFile
                local_dir = self.backup_dir

                if(self.ssh_pw is None):
                    subprocess.check_call(
                        ['scp', '-P', str(self.ssh_port), '-o', 'StrictHostKeyChecking no', remote_path, local_dir])
                else:
                    subprocess.check_call(
                        ['sshpass', '-p', self.ssh_pw, 'scp', '-P ', self.ssh_port, '-o', 'StrictHostKeyChecking no', remote_path, local_dir])
                status = 0
                printlog("WA: do_transfer_file returns [%s] " % (local_dir+ os.sep + os.path.basename(packageFile)))
                return [status, local_dir+ os.sep + os.path.basename(packageFile)]

            except (subprocess.CalledProcessError, OSError) as e:
                printlog("WA: do_transfer_file ssh error")
                print(e)
                status = 1

        return [status]


if __name__ == "__main__":

    printlog("WA: Running: %s" % ' '.join(sys.argv[0:]))
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
    parser.add_option("-m", "--mtimeout", default=0, type='int',
                      action="store", dest="mtimeout", help="mtimeout (default=0, no timeout)")
    parser.add_option("-r", "--retries", default=30, type='int',
                      action="store", dest="retries", help="retries for kubectl calls (default=30)")
    parser.add_option('-d', '--debug', default=3, action='store', type='int',
                      help="debug level(3), 1=ERROR, 2=WARN, 3=INFO, 4=DEBUG", metavar="LVL")
    (options, args) = parser.parse_args()

    host_p = 'tcp://' + options.host + ':' + str(options.port)
    workloadagent = WorkloadAgent(cert_dir=options.cert_dir,
                         ua_nodeType=options.node_type,
                         host_port=host_p,
                         delta_cap=options.cap,
                         enable_delta=(options.disable_delta is False),
                         debug=options.debug,
                         backup_dir = options.backup_dir,
                         cache_dir = options.cache,
                         ready_download=options.ready_download)

    workloadagent.ssh_host = options.host
    workloadagent.ssh_user = options.ssh_user
    workloadagent.ssh_pw = options.ssh_pw
    workloadagent.ssh_port = options.sshport
    workloadagent.cache = options.cache
    workloadagent.backup = options.backup_dir
    workloadagent.instdir    = options.wa_dir
    workloadagent.schema    = options.json
    workloadagent.mtimeout = options.mtimeout
    retry_wait_run_kubectl_cmd = options.retries

    if not os.path.exists(workloadagent.instdir):
        os.makedirs(workloadagent.instdir)

    if not os.path.exists(workloadagent.cache):
        os.makedirs(workloadagent.cache)

    if not os.path.exists(workloadagent.backup):
        os.makedirs(workloadagent.backup)

    workloadagent.run_forever()

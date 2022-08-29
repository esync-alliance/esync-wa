## Excelfore eSync on SOAFEE Framework Workload Agent Developer Notes

### Overview

The workload agent is an eSync update agent that uses kubectl CLIs to pull docker images and deploy them to the kubernetes cluster. The workload agent registers to the eSync client, which is running in its own container in the k3s cluster.
The eSync client connects to the eSync server via secure network connection. When a campaign is deployed from the eSync server, the eSync client invokes various callback functions of the workload agent to download, install, and do other update-related operations for the kubernetes cluster.
The component package that is downloaded from the eSync server contains JSON file which lists the kubernetes YAML files to update, as well as the YAML files referenced in the JSON file.
The docker image that is referenced in the YAML files are pulled from the docker repository, not from the eSync server.

### Build Environment Setup

Refer to the README.md file of `meta-xl4esync-soafee` layer to learn how to create the Demo Setup for SOAFEE Workload agent.

### Workload Agent

#### About the eSync Agent Library

##### General eSync Agent Library
The eSync Agent library builds on top of the xl4bus C library (libxl4bus) and encapsulates initialization, application protocols, JSON message parsing, and encoding.
eSync Agent library provides a straightforward interface to enable the rapid deployment of device-specific eSync Agents. In most cases, eSync Agent developers should only need to hook up the code needed to flash/update its device software with a package archive provided by the library.

#####  C Based Model
eSync Agent Library APIs serve as callback methods. eSync Agent developers shall provide function hookups to these callbacks. The function hookups are invoked in a predefined stage to carry out device-specific operations.

##### Python Based Model
eSync python-libua Library APIs serve as callback methods. eSync agent python developers shall provide function hookups to these callbacks. The function hookups are invoked in a predefined stage to carry out device-specific operations.

#### Workload Agent Python Script
The workloadagent.py python script is the implementation of the workload agent, which uses eSyncUA class from esyncua.py to interface with the eSync Agent C library.

##### Callback Methods

* `do_init()`
    + [Optional] Interface to allow device specific initialization, this is
    called before initializing xl4bus.
    Use this function to customize device  initialization before starting the update agent.
    + Args: None
    + Returns: None
* `do_confirm_download(pkgName, version)`
    + [Optional] Interface to confirm/deny download after UA receives `xl4.ready-download` message
    + Args:
        - `pkgName`: Component package name.
        - `version`: version string.
    + Returns:
        - Subclass shall return one of the status strings: `"DOWNLOAD_POSTPONED", "DOWNLOAD_DENIED", "DOWNLOAD_CONSENT"`
        - Default is `DOWNLOAD_CONSENT`

* `do_pre_install(downloadFileStr)`
    + [Optional] Interface to prepare for updating after UA receives `xl4.ready-update` message
    + Args:
        - `pkgName`: Component package name.
        - `version`: version string.
    + Returns:
        - Subclass shall return one of the status strings `"INSTALL_IN_PROGRESS", "INSTALL_FAILED"`
        - Default is `INSTALL_IN_PROGRESS`
* `do_install(version, packageFile)`
    + [Required] Interface to start updating after do_pre_install() upon receiving xl4.ready-update message.
    + Args:
        - `downloadFileStr`: Full pathname of the installation package file.
    + Returns:
        - Subclass shall return one of the status strings `"INSTALL_COMPLETED", "INSTALL_FAILED"`
        - Default is `INSTALL_COMPLETED`
* `do_post_install(packageName)`
    + [Optional] Interface to invoke additional action after `do_install()`
    + Args:
        - packageName: component package name.
    + Returns: None
* `do_get_version(packageName)`
    + [Optional]  Interface to retrieve current version of UA
    + Args:
        - `packageName`: component package name.
    + Returns:
        - list of two items `status, "version"`
            - `status(int)`: 0 for success, 1 for error.
            - `version(str)`: Version string.
* `do_set_version(packageName, ver)`
    + [Optional] Interface to set version of UA after successful update.
    + Args:
        - `packageName(str)`: A string for component package name found in `xl4.ready-update` message.
        - `ver(str)`: A version string found in `xl4.ready-update` message.
    + Returns:
        - `int`: 0 for success, 1 for error.
* `do_prepare_install(packageName, version, packageFile)`
    + [Optional] Interface to allow UA to manage `packageFile` after receiving `xl4.prepare-update`.
        e.g. A system might need to copy `packageFile` to a specific directory. In such case, UA shall return the new pathname, which will be passed to do_install.
    + Args:
        - `packageName(str)`: Component package name.
        - `version(str)`: Version string.
        - `packageFile(str)`: Full file path of downloaded package file.
    + Returns:
        - A list of one or two strings `"status", "newPath"`
            - status(str): required, one of `"INSTALL_READY", "INSTALL_FAILED"`
            - newPath(str): optional, only return newPath to inform the new file pathname should be used for installation in do_install.
* `do_transfer_file(packageName, version, packageFile)`
    + [Optional] Interface to allow UA to transfer `packageFile` from a remote system to the local filesystem for installation, after receiving . UA shall return the new local pathname, which will be used for further processing. Note that this inteface is invoked after receiving `xl4.prepare-update`, before calling `do_prepare_install`
    + Args:
        - `packageName(str)`: Component package name.
        - `version(str)`: Version string.
        - `packageFile(str)`: Full file path of downloaded package file.
    + Returns:
        - A list of one or two strings `status, "newPath"`.
            - `status(int)`: required, 0 for success, 1 for error.
            - `newPath(str)`: optional, only return newPath to inform the new file pathname should be used for further processing.
* `do_dmc_presence()`
    + [Optional] This is called when UA library detects that DMClient is connnected to eSync Bus.
    + Args: None
    + Returns
        - 0 for Success, 1 for Failure.

##### Arguments to Workload Agent Script

* The following arguments can be passed to `workloadagent.py`:
    + `cert(str)`: Top directory of UA certificates
    + `type(str)`: Type of end device (ECU) for which a custom agent has been developed
    + `host(str)`: Host url where eSync client is running
    + `port(str)`: TCP port where eSync bus is listening
    + `user(str)`: User name for ssh service where eSync client is running
    + `pass(str)`: Password for ssh service where eSync client is running
    + `sshport(str)`: TCP Port for ssh service where eSync client is running
    + `cap(str)`: Unused
    + `temp(str)`: Cache directory
    + `back(str)`: Backup directory
    + `load(str)`: Unused
    + `delta(str)`: Unused
    + `wa_dir(str)`: "workload agent install directory
    + `json(str)`: Path to workload agent schema JSON file
    + `debug(str)`: Unused

#### Dependencies

This package depends on the following python modules:
    + pylibua
    + optparse
    + json
    + jsonschema
    + subprocess
    + sys
    + zipfile
    + glob
    + yaml

### Contents of the Component Package

Refer to the docs/TestNotes.pdf file of `meta-xl4esync-soafee` layer to learn how to create the Component Package for SOAFEE Workload agent.


### Setup environment for testing

#### Pre-requisites
  1. Request Access to eSync Server (Ex url: https://soafee-esync-demo.excelfore.com/sotauiv4/#/login)
  2. Request Access to the Excelfore Docker Registry (Ex url: https://gitlab.excelfore.com/xl4-devops/deployment/customer/soafee-japan/)
  3. Upload component and create campaign
  4. Login to the Excelfore Docker Registry

#### Demo Test Setup

Refer to the TestNotes.pdf file to learn how to setup the Demo Setup test environment.


# OVERVIEW

sync_to_azure is a script for synchronizing MiSeq/NextSeq runs to Azure
blob storage. Given a source folder (--main-folder) containing individual runs
in sub-folders, the script will synchronize each sub-folder to azure, verify
the integrity of remote files by comparing MD5 hashes, and optionally delete
local files if files were successfully transferred and validated (with
--remove-source).

Completed runs may be detected by checking for the existence of user-defined
files, such as "RTAComplete.txt" for MiSeq and "RunCompletionStatus.xml" for
NextSeq v2 (with --completion-flag).

In addition to synchronizing folders containing sequencing runs, the script
can optionally copy sample-sheet files located in a separate folder; for a
given run ${NAME} the sample-sheet is expected to be named ${NAME}.csv.

# DOCKER IMAGE

The docker image requires that the `azure-storage-azcopy` submodule has been checked out. If that is not the case, the submodule can be initialized as follows:

``` bash
$ git submodule update --init azure-storage-azcopy/
```

Note that the submodule is currently setup using an SSH URL (`git@github.com/`) and therefore requires that the user has added a public SSH on github. If this is not done, the `submodule update` command will fail with permission denied errors.

To build an image with a tag based on the current commit:

``` bash
$ make
# or
$ make build
```

The image can be pushed to the CFB container registry with

``` bash
$ make push
```

By default, the short form of the current commit hash will be used as the tag for the docker image. This can be overridden by setting the `TAG` variable:

``` bash
$ make TAG=MyTag
$ make push TAG=MyTag
```

**WARNING:** Please make sure that all current changes have been committed before building a docker image for deployment!


# MANUAL INSTALLATION

``` bash
$ python3 setup.py install
$ sync_to_azure -h
```

Optional pretty logs:

``` bash
$ python3 -m pip install coloredlogs
```

## AZCOPY

This script depends on a modified version of AzCopy that adds a 'list_md5s'
command for the bulk retrieval of MD5 hashes of uploaded:

``` bash
$ sudo apt-get install golang
$ git clone https://github.com/biosustain/azure-storage-azcopy.git
$ cd azure-storage-azcopy
$ git checkout list_md5s
$ go build
```

Place the resulting executable, 'azure-storage-azcopy', in your PATH. If 'go
build' fails while fetching dependencies, you may need to set a GOPATH:

``` bash
$ export GOPATH=$HOME/go
```

# CONFIGURATION

The sync_to_azure script may be configured via command-line options,
or using a ini file via --config-file. By default, the script will look for
'azsync.cfg' in the current working directory:

``` toml
tenant-id =
application-id =
storage-account = cfbngsv2
container-name = nextseq01
credentials = /home/cfbngssync/config/credentials.txt

main-folder = /cifs/nextseq.clients.net.dtu.dk/NextSeqOutput/
samplesheet-folder = /cifs/nextseq.clients.net.dtu.dk/NextSeqSampleSheets/
completion-flag = RunCompletionStatus.xml

destination = NextSeqOutput

log-file = /home/cfbngssync/config/logs/nextseq.log
log-recipient =
azcopy-logs = /home/cfbngssync/config/logs/nextseq/

smtp-user = cfb-datalake-upload@win.dtu.dk
smtp-password =
smtp-host = mail.dtu.dk
smtp-port = 587
```

Options in the config file correspond to the options available via the command
line (see 'sync_to_azure --help'), but without the leading dashes.

# LOGGING

By default the script will write all output to STDOUT, but the --log-file
option may be used to save a copy to a given file. In addition, if the
--log-recipient and --smth-\* options are set, the log will be emailed to
the specified recipients if any errors occur.

# DEVELOPMENT

Code was formatted using [Black](https://github.com/psf/black) and checked using
[flake8](http://flake8.pycqa.org/en/latest/). Unit tests and regression tests are included and can be run using `tox`:

``` bash
$ cd container
$ tox
```

# OVERVIEW

This folder contains configuration files and scripts for setting up the VM used to sync files to the datalake, along with other tasks.

## BASIC REQUIREMENTS

The VM must have `autofs`, Docker and the Azure command-line tools (`az`) installed. In addition, `az` must be used to login using an account with access to the `cfbregistry` ACR. The `cfb_acr_reader` service principal is intended for this purpose (see below). Python modules used by `cronbeat` must either be install globally or in a virtual environment.

## AUTO-MOUNTING NETWORK DRIVES

1. Install `autofs`:

``` bash
$ sudo apt-get install autofs
```

2. Add the following line to the end of `/etc/auto.master`:

```
/net /etc/auto.nfs --timeout=300
```

3. Add mount-points to `/etc/auto.nfs`:

```
MiSeqOutput          -fstype=cifs,vers=2.1,ro,credentials=/etc/creds/MiSeqOutput.txt    ://10.75.2.164/MiSeqOutput/
NextSeqOutput        -fstype=cifs,vers=2.1,ro,credentials=/etc/creds/NextSeqOutput.txt  ://10.75.2.163/NextSeqOutput/
NextSeqSampleSheets  -fstype=cifs,vers=2.1,ro,credentials=/etc/creds/NextSeqOutput.txt  ://10.75.2.163/NextSeqSampleSheets/

Proteomics           -fstype=cifs,vers=2.1,ro,credentials=/etc/creds/Proteomics.txt     ://CFB-pFile01.win.dtu.dk/LabData/CFB/Instrument_Data/Exploris\ 480\ FSHPNR2/Data/
```


3. Save credentials in at the locations specified in `/etc/auto.nfs`, e.g:

``` bash
$ cat /etc/creds/NextSeqOutput.txt
username=
password=
```

4. Restart autofs:

``` bash
$ /etc/init.d/autofs restart
```

Mount points should now be accessible via `/net/MiSeqOutput`, etc:

``` bash
$ ls /net/Proteomics/
Prot27 Prot28 Prot29 [snip]
```

## GRANTING ACCESS TO THE CFB DOCKER REGISTRY

Docker on the VM needs access to the CFB docker registry (`cfbregistry.azurecr.io`). Scripts obtain temporary access to the ACR via the `az acr login` command. For that to work, login as the `cfb_acr_reader` app using `az login` on the VM:

``` bash
az login --service-principal --tenant f251f123-c9ce-448e-9277-34bb285911d9 --username bf6564d4-1e66-41e3-915e-b1fa347b1c55
```

This stores credentials for the service principal on the VM.

## BUILDING AND PUSHING CONFIG FILES AND DOCKER IMAGES

The `Makefile` included in this directory automates building, tagging, and pushing of docker images used by the VM. In addition, the makefile generates updated wrapper scripts that invoke the current version of the images and rsyncs these to the VM.

In addition, the makefile will push configuration file templates to the VM. Existing configuration files are not overwritten.

``` bash
# Build utility files and images
make build
# Build and push utility files and images
make push
```

The images tagged using the short git hash for the current commit. Configuration files are currently expected to be placed in `~/config/` on the VM and utility scripts and files are expected to be placed in `~/utils`.

## CONFIG FILES

On the server side, all configuration files in `~/config` must be updated once copied there. In addition, a `~/cronbeat.ini` file must be created with a `webhook` value specified (see `cronbeat/README.md`).

## CRON JOBS

An example crontab file is included in `utils`:

``` bash
# replace existing crontab
$ crontab ~/utils/crontab
```

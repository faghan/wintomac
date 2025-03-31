# TROUBLESHOOTING

## Revoked key when running in tmux

When running the script in a (detached) tmux session, azcopy calls will start
failing with with the message "failed to get keyring during saving token, key
has been revoked". This can be fixed (temporarily) calling

    $ keyctl session

This problem does not occur when running azcopy as part of a cron-script.

See the following issue for more information

https://github.com/Azure/azure-storage-azcopy/issues/561

## Login successful, but azure-storage-azcopy not logged in during subsequent actions

**Symptoms**

``` bash
$ azure-storage-azcopy login [...]
INFO: SPN Auth via secret succeeded.
$ azure-storage-azcopy list [...]
no SAS token or OAuth token is present and the resource is not public
$ azure-storage-azcopy logout
Error: failed to perform logout command, no cached token found for current user
```

This problem can normally be solved by creating a `keyctl` session before running `sync_to_azure`/`azure-storage-azcopy`:

``` bash
$ keyctl session new_session
$ sync_to_azure [...]
```

Note that intermittent failures of this type may occur when running the docker image. The cause is currently unknown, but they have usually resolved themselves by the next time the script is run.

**Additional information**

https://github.com/Azure/azure-storage-azcopy/issues/452


## Failed to get keyring during saving token, operation not permitted

The `azure-storage-copy login` command requires access to the `keyctl` API. This API is, however, blacklisted by Docker by default for security reasons. A modified seccomp profile is provided that whitelists API calls `add_key`, `keyctl`, and `request_key`. To use this profile, run Docker as follows

``` bash
$ docker run --security-opt seccomp=seccomp_profile.json [...]
```

## FileNotFoundError: [Errno 2] No such file or directory: '/data/NextSeqOutput'

This error is expected to occur occasionally, due to the sequencing machines being turned off. No action is needed unless this error persists for a longer period of time. In that case, contact the NGS group to determine the status of the instrument trying to debug the problem.


## Data / Samplesheet was never synced for old NGS run

The 'ngs' command records all observed runs, identified by folders in the `--main-folder` and samplesheets in the `--samplesheet-folder`, if specified. If a run has not been completed within 48 hours (and every 48 hours after that), a warning message is triggered.

To resolve this, ensure that the missing (or incomplete) data or samplesheet is available and re-run the sync script. In cases where data was removed from the instrument before the sync-script was run, it can be obtained from the AIT hosted backups.

It is recommended to create a scratch folder containing just the data to be synced if syncing from AIT backups. The wrapper script from `datalake-sync-vm` can be used to run `sync_to_azure` on any folder, provided that the layout matches the `/net/` auto-mount folder on the VM.

Full example for NextSeq run `201103_NB501016_0297_AH7GHCAFX2`:

``` bash
# Create scratch folder containing just the run we want to sync; this folder will be
# available as /data/ in the docker image and match the layout of auto-mounted drives.
# See the corresponding config.ini file for the expected the directory structure
$ mkdir -p ~/scratch/NextSeqOutput/201103_NB501016_0297_AH7GHCAFX2
$ mkdir -p ~/scratch/NextSeqSampleSheets/2020/
# Mount AIT backup storage
$ sudo mkdir -p /mnt/next-seq/
$ sudo mount -t cifs //ait-phnas02.win.dtu.dk/next-seq$ /mnt/next-seq/ -o username="${DTU_USERNAME}@win.dtu.dk",vers=2.1,ro
# Bind run to be synced in scratch folder; symlinks cannot be used for this because
# current versions of `azure-storage-azcopy` simply skips those.
$ sudo mount --bind /mnt/next-seq/NS\ Raw\ Data/NextSeqRaw2020/201103_NB501016_0297_AH7GHCAFX2/ ~/scratch/NextSeqOutput/201103_NB501016_0297_AH7GHCAFX2
# Make local copy of SampleSheet. This ensures that no already synced runs are marked as
# missing if the database of sync runs (`states.db`) post-date any of these runs.
$ cp /net/NextSeqSampleSheets/2020/201103_NB501016_0297_AH7GHCAFX2.csv ~/scratch/NextSeqSampleSheets/2020/
# Run the actual sync, mounting ~/scratch/ as /data/
$ ~/utils/datalake-sync ngs ~/config/nextseq-sync/ ~/scratch/
$ sudo umount ~/scratch/NextSeqOutput/201103_NB501016_0297_AH7GHCAFX2
$ sudo umount /mnt/next-seq
```

Full example for MiSeq run `201127_M02023_0583_000000000-J7HPH` (see comments above):

``` bash
$ mkdir -p ~/scratch/MiSeqOutput/201127_M02023_0583_000000000-J7HPH
$ sudo mkdir -p /mnt/mi-seq/
$ sudo mount -t cifs //ait-phnas02.win.dtu.dk/mi-seq$ /mnt/mi-seq/ -o username="${DTU_USERNAME}@win.dtu.dk",vers=2.1,ro
$ sudo mount --bind /mnt/mi-seq/MS\ Output/2020/201127_M02023_0583_000000000-J7HPH/ ~/scratch/MiSeqOutput/201127_M02023_0583_000000000-J7HPH
$ ~/utils/datalake-sync ngs ~/config/miseq-sync/ ~/scratch/
$ sudo umount ~/scratch/MiSeqOutput/201127_M02023_0583_000000000-J7HPH
$ sudo umount /mnt/mi-seq
```

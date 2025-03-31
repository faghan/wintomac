#!/bin/bash
/usr/bin/blobfuse $1 --tmp-path=/mnt/resource/blobfusetmp -o attr_timeout=240 -o entry_timeout=240 -o negative_timeout=120 -o allow_other --config-file=/home/avmillumina/data-lake/ngs/avm-illumina-run/fuse_connection_miseq01.cfg

.PHONY: check_vars build build_utils build_images push push_utils push_images

HOST := cfbngssync@nnfcb-p0001.win.dtu.dk
# Tag to be used for newly generated Docker images
TAG := $(shell git log --pretty=format:'%h' -n 1)


build: build_utils build_images


build_utils: check_vars
	rm -rf deployment
	cp -av utils deployment

	# Update wrapper scripts for datalake-sync, incyght-sync, etc.
	sed -i -e"s#:TAG#:${TAG}#" \
		deployment/datalake-sync \
		deployment/incyght-sync \
		deployment/monitor-ncbi-mappings \
		deployment/monitor-proteomics

	# seccomp profile needed to whitelist `keyctl`
	cp ../datalake-sync/seccomp_profile.json deployment/

	# cronbeat: statistics and notification wrapper for cron tasks
	cp ../cronbeat/cronbeat.py deployment/cronbeat
	cp ../cronbeat/requirements.txt deployment/


build_images:
	make -C ../incyght-sync TAG=${TAG}
	make -C ../datalake-sync TAG=${TAG}
	make -C ../monitor-ncbi-mappings TAG=${TAG}
	make -C ../monitor-proteomics TAG=${TAG}


push: push_utils push_images


push_utils: build_utils
	# Configuration file templates (replace all "..." with proper values)
	rsync -av --ignore-existing ./config/ ${HOST}:~/config/
	# Scripts and static configuration files
	rsync -av --delete ./deployment/ ${HOST}:~/utils/


push_images: build_images
	az acr login --name cfbregistry
	docker push cfbregistry.azurecr.io/incyght-sync:${TAG}
	docker push cfbregistry.azurecr.io/datalake-sync:${TAG}
	docker push cfbregistry.azurecr.io/monitor-ncbi-mappings:${TAG}
	docker push cfbregistry.azurecr.io/monitor-proteomics:${TAG}


check_vars:
ifeq (${TAG},)
	$(error TAG is not set; use "make [target] TAG=v1" with an appropriate version)
endif

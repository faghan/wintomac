.PHONY: check_vars build push pull

IMAGE := cfbregistry.azurecr.io/pasx_savvy_sync
TAG := $(shell git log --pretty=format:'%h' -n 1)
ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))


# default target first
build: check_vars
	docker build . --tag ${IMAGE}:${TAG}

push: check_vars
	az acr login --name cfbregistry
	docker push ${IMAGE}:${TAG}

pull: check_vars
	az acr login --name cfbregistry
	docker pull ${IMAGE}:${TAG}

run: check_vars
	docker run -it -v ${ROOT_DIR}/logs:/logs --rm ${IMAGE}:${TAG}

check_vars:
ifeq (${TAG},)
	$(error TAG is not set; use "make [target] TAG=v1" with an appropriate version)
endif

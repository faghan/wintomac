.PHONY: check_vars build push pull test deploy

IMAGE := cfbregistry.azurecr.io/data_broker
TAG := $(shell git log --pretty=format:'%h' -n 1)


# default target first
build: check_vars
	docker build . --tag ${IMAGE}:${TAG} #--squash

push: check_vars
	az acr login --name cfbregistry
	docker push ${IMAGE}:${TAG}

pull: check_vars
	az acr login --name cfbregistry
	docker pull ${IMAGE}:${TAG}

test: check_vars
	docker run --rm --name databroker --env-file Docker.env -p 80:80 ${IMAGE}:${TAG}

runserver:
	./manage.sh runserver

check_vars:
ifeq (${TAG},)
	$(error TAG is not set; use "make [target] TAG=v1" with an appropriate version)
endif

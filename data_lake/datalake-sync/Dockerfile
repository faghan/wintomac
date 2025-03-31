FROM golang:1.15.3-alpine
ENV PYTHONUNBUFFERED=1

WORKDIR /container

COPY ./azure-storage-azcopy /container/azure-storage-azcopy
RUN cd /container/azure-storage-azcopy/ \
    && go build \
    && cp azure-storage-azcopy /usr/bin/ \
    && rm -rf ~/.cache/go-build

# keyutls required for 'keyctl', needed for `azure-storage-azcopy` logins
RUN apk add python3 python3-dev py3-pip gcc keyutils musl-dev libffi-dev openssl-dev

# requirements are copied by itself, to avoid re-running pip for changes in other files
COPY ./container/requirements.txt .
# `--ignore-installed distlib` is required to workaround pip refusing to uninstall
# packages installed via distlib. Google "Cannot uninstall distlib" for information.
RUN pip install --no-cache-dir -r ./requirements.txt --ignore-installed distlib

RUN apk add bash

COPY ./container .
RUN python3 setup.py install

ENTRYPOINT ["bash", "./start.sh"]
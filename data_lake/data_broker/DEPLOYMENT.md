# Setting up Azure VM

## Network settings

**IMPORTANT:** Expose **only** port 443 (HTTPS) and optionally port 22 (SSH) using the Azure portal.

Do not expose port 80 (HTTP), as HTTP connections made to this port will expose API keys as part of the GET request, even if nginx has been configured to redirect to HTTPS.

## Setting up Debian 10 image

The following assumes a Debian 10 image with Docker installed. The current user must be added to the `docker` group. If they are not, run the following and then logout/login before proceeding:

``` bash
sudo usermod -a -G docker $USER
```

### 1. Accessing the docker registry

The `az` tool is needed to authenticate with the CFB docker registry on Azure:

``` bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

Next, login as the `cfb_acr_reader` app using `az login` command on the VM:

``` bash
az login --service-principal --tenant f251f123-c9ce-448e-9277-34bb285911d9 --username bf6564d4-1e66-41e3-915e-b1fa347b1c55
```

Once this is done, you can temporarily login to the Azure Docker registry as follows:

``` bash
az acr login --name cfbregistry --resource-group rg-cfb-common
```

The `az acr login` credentials only lasts for a few hours and it is therefore necessary to login every time you wish to run/pull a new image.

### 2. Create mounted folders

The following folders are will be used by the docker image to persist files:

``` bash
mkdir letsencrypt logs
```

If available, place current letsencrypt tarball ( `live.tgz` ) in the `letsencrypt` folder. If not available, if certificate has expired, or if domain has changed, then see the section on Let's Encrypt deployment below once the docker image has been started.

Create a `Docker.env` file from the `template.yaml` file from the data-broker repository and fill in the `AZURE_CLIENT_SECRET` for the given `AZURE_CLIENT_ID`. This client is expected to be able to access a number of keys in the key-vault specified in AZURE_KEY_VAULT (see `start.sh` in the `container` folder).


### 3. Run docker image

Run docker with the appropriate image version:

``` bash
az acr login --name cfbregistry --resource-group rg-cfb-common
docker run --detach -p 80:80 -p 443:443 --name databroker --env-file Docker.env --mount type=bind,source="$(pwd)/letsencrypt",target=/broker/letsencrypt --mount type=bind,source="$(pwd)/logs",target=/var/log cfbregistry.azurecr.io/data_broker:v6
```

It may be helpful to first run docker with the `--detach` option replaced with `--rm` , to allow simple confirmation of a successful startup and direct access to STDOUT during debugging.

## Upgrading docker image

Pull the updated image from the docker container registry.

``` bash
az acr login --name cfbregistry --resource-group rg-cfb-common
docker pull cfbregistry.azurecr.io/data_broker:v7
```

Terminate and remove the current container:

``` bash
docker stop databroker
docker rm databroker
```

Finally, run the docker image as described in the "Run docker image" section using the updated image.

## Setting up Let's Encrypt for HTTPS

If this is the first time setting up letsencrypt, add a rule granting access to the VM on port 80 using the Networking tab on the Azure portal.

Connect to running docker image:

``` bash
docker exec -it databroker bash
```

Run certbot and follow instructions and then run `letsencrypt.sh` to backup certificate files:

``` bash
certbot --nginx
bash /broker/letsencrypt.sh
```
Use the `--force-renewal` option for `nginx` if the domain has changed (`nginx.conf` must also be updated). Finally, use the Azure portal to revoke the Networking rule granting access to port 80 on the VM.

The `letsencrypt.sh` creates a rolling backup of the current certificate in the `letsencrypt` folder created above. The current, active certificate is found in the `live.tgz` tarball.

### Certificate renewal

Automatic certificate renewal is possible using certbot (see comments in `container/start.sh`), but this requires that port 80 is open. Opening port 80, however, allows for end users to accidentally send API keys over plain-text, even if redirection to HTTPS is enabled.

For this reason, certificate renewal should be performed by hand, by first opening port 80 via the Azure portal and then running

``` bash
    docker exec -it databroker bash
    certbot renew
    bash /broker/letsencrypt.sh
```

Remember to close port 80 once the certificate has been renewed.

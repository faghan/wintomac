# JupyterHub on Kubernetes

The following is based on the documentation at <https://zero-to-jupyterhub.readthedocs.io/en/latest/index.html>.

To create a Kubernetes cluster, add a 'Kubernetes Service' to a resource group; default parameters are fine. Alternatively, follow instructions in "Kubernetes on Microsoft Azure Kubernetes Service (AKS)" (see link above) to perform setup via CLI.

Only create a single nodepool during initial setup and see below for how to create a nodepool for user pods.

## Setting up Helm

Helm 3 is already installed on Azure Kubernetes clusters, so the installation and setup of Helm should be skipped.

## Installing JupyterHub

Follow the "Setup JupyterHub" instructions in the official documentation, using a copy of the `template.yaml` file in this repository as the basis for the `config.yaml` file. However, do read the following steps first and apply before/while deploying JupterHub.

Constants used during deployment:

``` bash
NAMESPACE="jhub"
# Name given to Kubernetes cluster created on Azure
CLUSTER="jupyterhub"
# Automatically generated resource created for ${CLUSTER} on Azure
RESOURCE_GROUP="MC_rg_Jupyter_jupyterhub_northeurope"
# Version of JupyterHub Helm chart; see https://jupyterhub.github.io/helm-chart/
VERSION="1.1.3"
```

### 1. Setup HTTPS via Let's Encrypt

JupyterHub on Kubernetes supports Let's Encrypt out of the box. A `contactEmail` address is required to be specified in the `config.yaml` file for this purpose:

``` yaml
proxy:
  https:
    hosts:
      - cfbjupyter.northeurope.cloudapp.azure.com
    letsencrypt:
      contactEmail: YOUR_EMAIL_HERE
```

If there are issues during certificate signing, the server will fall back to a self-signed certificate. To troubleshoot the Let's Encrypt process, view the process log using `kubectl`:

``` bash

$ kubectl get pod -n ${NAMESPACE}
NAME                              READY   STATUS    RESTARTS   AGE
autohttps-6cfc49b9dc-c4z4m        2/2     Running   1          5d19h
...
$ kubectl logs autohttps-6cfc49b9dc-c4z4m traefik
```

### 2. Enable login via Azure Active Directory

To enable login via Azure AD, register an app for the login:

https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade

Under "Authentication", click "Add a platform", select "Web" and then enter the following Redirect URL, using the appropriate domain name, e.g. `https://cfbjupyter.northeurope.cloudapp.azure.com/hub/oauth_callback`. Once created, generate a client secret under "Certificates & secrets".

Next, limit access to relevant users and groups as described in the [Restrict your Azure AD app to a set of users in an Azure AD tenant](https://docs.microsoft.com/en-us/azure/active-directory/develop/howto-restrict-your-app-to-a-set-of-users) How-To. Limit access to the group `CFB-All (NNFCB)`.

The app will also need the Microsoft Graph `User.Read` API permission. For this to work for regular users, the Azure administrator (AIT) will need to grant consent on behalf of users.

``` yaml
auth:
  type: azuread
  azuread:
    clientId: "CLIENT_ID_HERE"
    clientSecret: "CLIENT_SECRET_HERE"
    tenantId: "TENANT_ID_HERE"
    callbackUrl: "https://cfbjupyter.northeurope.cloudapp.azure.com/hub/oauth_callback"
```

By default, Azure AD login uses the `name` property as the username. However, `name` is a mutable, non-unique field, so the following `extraConfig` is used to instead use the User Principal Name as the username:

``` yaml
hub:
  extraConfig:
    00-azuread: |
      c.AzureAdOAuthenticator.username_claim = "upn"
```

Object ID (`oid`) is another alternative with stronger guarantees, but is less readable and makes finding owned objects harder. See the [Microsoft identity platform ID tokens](https://docs.microsoft.com/en-us/azure/active-directory/develop/id-tokens) documentation for available properties.

Client secret for registered app expires. When it does, the user would get 
`500 internal server error`. A new secret can be created on Azure portal > 
App registrations > CFB JupyterHub. New secret should be noted on `config.
yaml` and release should be updated as described on "Deploying JupyterHub" 
section.

### 3. Enable auto-scaling of nodes

Alternatively, see next step for using an independent user-only pool of nodes for the notebook pods (the recommended approach).

At the time of writing, the instructions for [Kubernetes on Microsoft Azure Kubernetes Service (AKS) with Autoscaling](https://zero-to-jupyterhub.readthedocs.io/en/latest/microsoft/step-zero-azure-autoscale.html) are not useful, as the Azure autoscaler will kill nodes too aggressively. Instead, enable the cluster autoscaler as described [here](https://docs.microsoft.com/en-us/azure/aks/cluster-autoscaler):

``` bash
$ az aks update --resource-group ${RESOURCE_GROUP} --name ${CLUSTER} --enable-cluster-autoscaler --min-count 1 --max-count 6
```

To update the min/max number of nodes:

``` bash
$ az aks update --resource-group ${RESOURCE_GROUP} --name ${CLUSTER} --update-cluster-autoscaler --min-count 1 --max-count 6
```

### 4. User-only pool of nodes

An independent pool of nodes can be used for user-pods This ensures that system pods wont be scheduled on those nodes, which would prevent the autoscaler from reclaiming them, along with other benefits.

The userpool (here named `userpool`) has to be created using the CLI, as the UI currently does not allow labels and taints to be set:

``` bash
$ az aks nodepool add \
  --resource-group ${RESOURCE_GROUP} --cluster-name ${CLUSTER} --name userpool \
  --enable-cluster-autoscaler --min-count 0 --max-count 5 --node-count 0 \
  --node-vm-size Standard_B4ms \
  --labels hub.jupyter.org/node-purpose=user \
  --node-taints hub.jupyter.org/dedicated=user:NoSchedule
```

The included `config.yaml` file has user pods `prefer` nodes from this node-pool:

``` yaml
userPods:
  nodeAffinity:
    matchNodePurpose: prefer
```

If `matchNodePurpose` is set to `require`, user nodes will always be scheduled in this nodepool.

### 5. Disable the Kubernetes dashboard

The documentation recommends disabling the Kubernetes dashboard or security reasons (<https://zero-to-jupyterhub.readthedocs.io/en/latest/administrator/security.html>). To permanently disable the dashboard, use the following command:

``` bash
$ az aks disable-addons --addons kube-dashboard --resource-group ${RESOURCE_GROUP} --name ${CLUSTER}
```

Verify that the dashboard pods are gone:

``` bash
$ kubectl get pods -n kube-system
```

### Deploying JupiterHub

The current version of the documentation installs JupyterHub version 0.9.0 (`--version=0.9.0`). However, pod creation on login is inconsistent for <0.10.0, for which reason a newer version is used (see above):

``` bash
$ helm upgrade --cleanup-on-fail --install jhub jupyterhub/jupyterhub --namespace ${NAMESPACE} --create-namespace --version=${VERSION} --values config.yaml
```

To redeploy with an updated `config.yaml` file or new JupyterHub release:

``` bash
$ helm repo update
$ helm upgrade --cleanup-on-fail jhub jupyterhub/jupyterhub --namespace ${NAMESPACE} --version=${VERSION} --values config.yaml
```

## Customizing JupyterHub environment

### Updating the example notebooks

``` bash
$ cd jupyter_service_sample_notebooks/
$ git pull
$ cd ..
$ git commit jupyter_service_sample_notebooks
```

### Building and pushing a custom docker image

A custom `Dockerfile` is included in the repository. This Dockerfile requires that the `croissance` and `jupyter_service_sample_notebook` submodules have been checked out. If that is not the case, the submodules can be initialized as follows:

``` bash
$ git submodule update --init croissance/
$ git submodule update --init jupyter_service_sample_notebooks/
```

Note that the sample-notebook submodule is currently setup using an SSH URL (`git@github.com/`) and therefore requires that the user has added a public SSH on github. If this is not done, the `submodule update` command will fail with permission denied errors.


Too build and push the image, simply run

``` bash
$ make
$ make push
```

By default, the the short form of the current commit hash will be used as the tag for the docker image. This can be overridden by setting the `TAG` variable:

``` bash
$ make TAG=MyTag
$ make push TAG=MyTag
```

Update `config.yaml` with the current tag and redeploy:

``` yaml
singleuser:
  image:
    name: "cfbregistry.azurecr.io/jupyterhub"
    tag: "636f5aa"
```

### Specifying docker image from private registry

To use a custom docker image, add the following to `config.yaml`; the `imagePullSecret` section should be updated to contain the admin credentials for the container registry containing the image. If the image is in a public registry, the `imagePullSecret` section should be omitted.

``` yaml
singleuser:
  image:
    name: "cfbregistry.azurecr.io/jupyterhub"
    tag: "636f5aa"

  imagePullSecret:
    enabled: true
    registry: "cfbregistry.azurecr.io"
    username: "cfbregistry"
    password: ...
```

Once added (or updated), redeploy as shown above.

### Persistent conda environments

By default, environments created in a JupyterHub session will not persist across sessions, meaning that additional dependencies installed by the user will be lost. To solve this, the [nb_conda_kernels](https://github.com/Anaconda-Platform/nb_conda_kernels/) extension is used to allow easy access to persistent, user-created conda environments.

The setup for this involves multiple components (all files are located in `container/`):

1. The `nb_conda_kernels` extension is installed using `conda` as part of the docker image creation.
2. A custom `jupyter_notebook_config.json` file is used to filter the list of conda environments enumerated by `nb_conda_kernels` , which would otherwise include duplicate entries for built-in environments.
3. A custom `.condarc` file is used to store new environments in the user's home folder, ensuring that these are persistent.
4. A script ( `setup.sh` ) is run when the user container is created (see `config.yaml` ); this script copies the above files to the appropriate folders in the user's home directory the first time it is run.

A new conda environment may be created by the user as follows:

``` bash
$ conda create -n myenv ipykernel scipy
```

Refresh the environment list and the new environment should be listed as `Python [conda env:myenv]` .

# Administration

## Deleting user storage

User storage is named using the UPN (see "Azure AD" section above). To remove user storage, locate the corresponding Persistent Volume Claim (pvc) and delete it. For example, for user miksch@win.dtu.dk:

``` bash
$ USERNAME=miksch
$ kubectl get pvc claim-${USERNAME}-40win-2edtu-2edk
NAME                            STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS       AGE
claim-miksch-40win-2edtu-2edk   Bound    pvc-f05b55b6-f3d9-4660-914c-79ea4b2740a3   10Gi       RWO            jupyter-user-hdd   37m
```

Use `kubectl delete pvc` to remove this claim:

``` bash
$ kubectl delete pvc claim-miksch-40win-2edtu-2edk
````

Note that the PVC wont be deleted while the corresponding pod is still running:

``` bash
$ USERNAME=miksch
$ kubectl get pods jupyter-${USERNAME}-40win-2edtu-2edk
NAME                              READY   STATUS    RESTARTS   AGE
jupyter-miksch-40win-2edtu-2edk   1/1     Running   0          39m
```

# Troubleshooting

See also the [Debugging](https://zero-to-jupyterhub.readthedocs.io/en/latest/administrator/debug.html) section of the documentation.

## Viewing cluster logs

The following command may be used to inspect the cluster log:

``` bash
$ kubectl -n ${NAMESPACE} get events --sort-by='{.lastTimestamp}'
```

## 'timed out waiting for the condition' while deploying

Deployment occasionally times out while fetching the docker images. Check the log for other errors (see above) and simply re-run the `helm` command. The `--timeout` option may also be used to increase the timeout, for example:

``` bash
$ helm upgrade --cleanup-on-fail jhub jupyterhub/jupyterhub --namespace ${NAMESPACE} --version=${VERSION} --values config.yaml --timeout 10m
```

## Shutting down virtual machines

Locate 'Virtual machine scale set' resource in resource group, select "Manual scale" under "Scaling" and set the number of nodes to 0. To restart the cluster, set the number of nodes to 1 or more.

It may be necessary to turn off the autoscaler beforehand:

``` bash
$ az aks update --resource-group ${RESOURCE_GROUP} --name ${CLUSTER} --disable-cluster-autoscaler
```

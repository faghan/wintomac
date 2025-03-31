# Data Warehouse REST API

## Authentication

User authentication is performed using an API key generated via the LIMS extension user-settings page. This key must be set in the header of REST API calls, as shown below.

To obtain an API key, visit https://lims.biosustain.dtu.dk/app/user-settings

###

## NGS

### List samples

Returns a list of Sequencing Submission Samples as JSON.

* **URL** `/ngs/samples` or `/ngs/samples?archived=:bool`

* **Method:** `GET`

* **URL Params**

  **Optional:**

  + `archived=[bool]`

    _List archived samples if set to "true", "1", or "yes"_

* **Success Response:**

  + **Code:** 200 <br />

    **Content:** `[{"antibody_if_chipseq": null, "archive_reason": null, "average_library_size_in_bp": null, "buffer": "M9 MM", "cell_line": null, "comments": null, "concentration_ngul": 1.0, "created_at": "2019-12-17T13:42:26.125749Z", "creator": "wally", "entity_registry_id": "SEQSUB1234", "experiment": "LIMS_1234", "files_url": "https://cfbdatabroker.northeurope.cloudapp.azure.com/ngs/files/wally_lims_s1", "is_archived": false, "modified_at": "2020-01-28T15:59:40.871874Z", "name": "wally_lims_s1", "nucleotide_type": "Amplicon DNA (aDNA)", "organism": "Saccharomyces wallyae", "organism_if_external": null, "parent_culture": null, "replicate": 1, "strain": null, "volume_ul": 1.0, "web_url": "https://biosustain.benchling.com/biosustain/f/lib_abc1DEfG-registry/abc_DEfGhijk-wally_lims_s1/edit"}, ...]`

    _Fields correspond to those of Sequencing Submission Samples. The additional field 'web\*url' links to the entity on the Benchling website and the field 'files_url' provides the REST API URL used to list files relating to a sample._

* **Error Response:**

  + **Code:** 403 FORBIDDEN <br />

    **Content:** `{ error : "Incorrect authentication credentials." }`

* **Sample Call:**

  Command-line:

``` bash
  curl -L -H "APIKEY: ${MY_API_KEY}" https://cfbdatabroker.northeurope.cloudapp.azure.com/ngs/samples/
```

  Python:

``` python
  import requests

  session = requests.Session()
  session.headers["APIKEY"] = MY_API_KEY

  response = session.get("https://cfbdatabroker.northeurope.cloudapp.azure.com/ngs/samples")
  response.raise_for_status()

  print(response.json())
```

### List files

Returns a list of files/folders belonging to a sample as JSON.

* **URL** `/ngs/files` or `/ngs/files/:path` or `/ngs/files?archived=:bool`

* **Method:** `GET`

* **URL Params**

  **Optional:**

  + `path=[string]`

    _List the files at the specified location/for the specified sample. If omitted, all samples are listed._

  + `archived=[bool]`

    _List archived samples if set to "true", "1", or "yes"_

* **Success Response:**

  + **Code:** 200 <br />

    **Content:** `[{"name":"reads/","type":"folder","url":"https://cfbdatabroker.northeurope.cloudapp.azure.com/ngs/files/Example_1/reads/"},{"name":"Example_1.ready","type":"file","size":0,"files":"https://cfbdatabroker.northeurope.cloudapp.azure.com/ngs/download/Example_1/Example_1.ready"}, ...]`

    _Enties represents either files or sub-folder. Sub-folders are viewed using this API endpoint, while files may be downloaded using the /ngs/download/ endpoint (see below)._

* **Error Response:**

  + **Code:** 403 FORBIDDEN <br />

    **Content:** `{ error : "Incorrect authentication credentials." }`

* **Sample Call:**

  Command-line:

``` bash
  curl -L -H "APIKEY: ${MY_API_KEY}" https://cfbdatabroker.northeurope.cloudapp.azure.com/ngs/files/
```

  Python:

``` python
  import requests

  session = requests.Session()
  session.headers["APIKEY"] = MY_API_KEY

  response = session.get("https://cfbdatabroker.northeurope.cloudapp.azure.com/ngs/files")
  response.raise_for_status()

  print(response.json())
```

### Downloading file

Download a file from the Data Lake.

* **URL** `/ngs/download/:path`

* **Method:** `GET`

* **URL Params**

  **Required:**

  + `path=[string]`

    _Download the file at the specified location._

* **Success Response:**

  + **Code:** 302 <br />

    **Content:**

    _A redirect to Azure file storage allowing for time-limited access to the requested resource._

* **Error Response:**

  + **Code:** 403 FORBIDDEN <br />

    **Content:** `{ error : "Incorrect authentication credentials." }`

  + **Code:** 404 FILE NOT FOUND <br />

* **Sample Call:**

  Command-line:

``` bash
  curl -L -H "APIKEY: ${MY_API_KEY}" https://cfbdatabroker.northeurope.cloudapp.azure.com/ngs/download/Example_1/reads/fastq/Example_1_S10_L004_R2_001.fastq.gz > Example_1_S10_L004_R2_001.fastq.gz
```

  Python:

``` python
    import requests

    session = requests.Session()
    session.headers["APIKEY"] = MY_API_KEY

    url = "https://cfbdatabroker.northeurope.cloudapp.azure.com/ngs/download/Example_1/reads/fastq/Example_1_S10_L004_R2_001.fastq.gz"
    response = session.get(url, stream=True)
    response.raise_for_status()

    with open("Example_1_S10_L004_R2_001.fastq.gz", "wb") as handle:
        for chunk in response.iter_content(1024):
            handle.write(chunk)
```

## Proteomics

### List requests

Returns a list of AC Proteomics requests as JSON.

* **URL** `/proteomics/requests`

* **Method:** `GET`

* **Success Response:**

  + **Code:** 200 <br />

    **Content:** `[{"creator": "example_user", "files_url": "https://cfbdatabroker.northeurope.cloudapp.azure.com/proteomics/files/PROT1234", "requestor": "example_user", "analytical_submission_samples": [...], "proteomics_submission_samples": [...], "created_at": "2020-02-01T16:43:17.868028Z", "request_status": "COMPLETED", "name": "PROT1234", "web_url": "https://biosustain.benchling.com/requests/req_ZPgfea3z", "expected_delivery_date": "2020-02-03", "expected_number_of_samples": 20, "comments": null, "scheduled_on": null, "comments_fulfiller": null}, ...]`

    _Fields correspond to those of AC Proteomics requests. The additional field `web_url` links to the entity on the Benchling website and the field `files_url` provides the REST API URL used to list files relating to a request. The `analytical_submission_samples` and `proteomics_submission_samples` contains lists of Benchling Analytical Submission Samples and Proteomics Submission Samples, respectively._

* **Error Response:**

  + **Code:** 403 FORBIDDEN <br />

    **Content:** `{ error : "Incorrect authentication credentials." }`



### List files

Returns a list of Sequencing Submission Samples as JSON.

* **URL** `/proteomics/files` or `/proteomics/files/:path`

* **Method:** `GET`

* **Success Response:**

  + **Code:** 200 <br />

    **Content:** `{"name":"etl/","type":"folder","url":"https://cfbdatabroker.northeurope.cloudapp.azure.com/proteomics/files/PROT1234/etl/"},{"name":"metadata.xlsx","type":"file","size":7825,"url":"https://cfbdatabroker.northeurope.cloudapp.azure.com/proteomics/download/PROT1234/metadata.xlsx"},{"name":"results.ready","type":"file","size":0,"url":"https://cfbdatabroker.northeurope.cloudapp.azure.com/proteomics/download/PROT1234/results.ready"},{"name":"results.xlsx","type":"file","size":6108437,"url":"https://cfbdatabroker.northeurope.cloudapp.azure.com/proteomics/download/PROT1234/results.xlsx"}]`

    _Enties represents either files or sub-folder. Sub-folders are viewed using this API endpoint, while files may be downloaded using the /proteomics/download/ endpoint (see below)._

* **Error Response:**

  + **Code:** 403 FORBIDDEN <br />

    **Content:** `{ error : "Incorrect authentication credentials." }`

### Downloading a file

Download a proteomics file from the Data Lake.

* **URL** `/proteomics/download/:path`

* **Method:** `GET`

* **URL Params**

  **Required:**

  + `path=[string]`

    _Download the file at the specified location._

* **Success Response:**

  + **Code:** 302 <br />

    **Content:**

    _A redirect to Azure file storage allowing for time-limited access to the requested resource._

* **Error Response:**

  + **Code:** 403 FORBIDDEN <br />

    **Content:** `{ error : "Incorrect authentication credentials." }`

  + **Code:** 404 FILE NOT FOUND <br />

using Azure.Identity;
using Azure.Storage.Blobs;
using Azure.Storage.Blobs.Models;
using DataLakeStats.Model;
using ExcelDataReader;
using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Data;
using System.IO;
using System.Linq;

namespace Cfb.DataLakeStats.Helpers
{
    /// <summary>
    /// Helper class for blob storage operations.
    /// </summary>
    internal class BlobStorageHelper
    {
        //https://docs.microsoft.com/en-us/azure/storage/blobs/storage-blobs-list?tabs=dotnet

        //https://github.com/Azure-Samples/storage-blob-dotnet-getting-started/blob/master/BlobStorage/Advanced.cs

        //https://docs.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-dotnet

        private readonly BlobServiceClient blobServiceClient;

        /// <summary>
        /// Initializes BlobStorageHelper and instansiates a new BlobServiceClient using DefaultAzureCredentials.
        /// </summary>
        /// <param name="accountName">The name of the blob storage account.</param>
        internal BlobStorageHelper(string accountName)
        {
            this.blobServiceClient = new BlobServiceClient(new Uri($"https://{accountName}.blob.core.windows.net"),
                                                           new DefaultAzureCredential());
        }

        /// <summary>
        /// Pages the blobs in the container from the specified prefix and calls back for each page.
        /// </summary>
        /// <param name="containerClient">An instanse of BlobContainerClient.</param>
        /// <param name="prefix">The blob path prefix to filter by.</param>
        /// <param name="callback">The callback action.</param>
        private void IterateBlobPages(BlobContainerClient containerClient, string prefix, Action<Azure.Page<BlobHierarchyItem>> callback)
        {
            string continuationToken = null;
            do
            {
                var resultSegment = containerClient.GetBlobsByHierarchy(prefix: prefix, delimiter: "/").AsPages(continuationToken);
                //loop result segments
                foreach (Azure.Page<BlobHierarchyItem> blobPage in resultSegment)
                {
                    callback(blobPage);

                    //get the continuation token and loop until it is empty.
                    continuationToken = blobPage.ContinuationToken;
                }
            } while (continuationToken != "");
        }

        /// <summary>
        /// Reads the blob as an Excel file and returns the number of rows in the Samples sheet
        /// </summary>
        /// <param name="container">An instance of ContainerClient</param>
        /// <param name="blobPath">The full path to the blob containing the Excel file</param>
        /// <returns>The number of rows in the "Samples" sheet</returns>
        private int GetProteomicsNumberOfSamples(BlobContainerClient container, string blobPath)
        {
            BlobClient blobClient = container.GetBlobClient(blobPath);
            DataSet dataSet;
            using (var stream = new MemoryStream())
            {
                blobClient.DownloadTo(stream);
                using var reader = ExcelReaderFactory.CreateReader(stream);
                dataSet = reader.AsDataSet(new ExcelDataSetConfiguration()
                {
                    ConfigureDataTable = (_) => new ExcelDataTableConfiguration()
                    {
                        UseHeaderRow = true,
                    }
                });
            }
            DataTable table = dataSet.Tables["Samples"];
            return table.Rows.Count;
        }

        /// <summary>
        /// Collects proteomics statistics.
        /// </summary>
        /// <param name="accountName">The name of the proteomics storage account.</param>
        /// <param name="containerName">The name of the container to collect stats in.</param>
        /// <returns>An instance of ProteomicsStats</returns>
        internal ProteomicsStats GetProteomicsStats(string containerName)
        {
            var containerClient = blobServiceClient.GetBlobContainerClient(containerName);

            int numberOfFolders = 0;
            int numberOfSamples = 0;
            var requestNames = new List<string>();

            IterateBlobPages(containerClient, "", (blobPage) =>
            {
                //if IsPrefix=true, we have a virtual folder
                var folders = blobPage.Values.Where(x => x.IsPrefix);
                numberOfFolders += folders.Count();

                //loop (virtual) folders in first level = request runs
                foreach (var folder in folders)
                {
                    IterateBlobPages(containerClient, folder.Prefix, (innerBlobPage) =>
                    {
                        string metadataSheetPath = folder.Prefix + "metadata.xlsx";
                        if (innerBlobPage.Values.Any(x => x.IsBlob && x.Blob.Name == metadataSheetPath))
                        {
                            numberOfSamples += GetProteomicsNumberOfSamples(containerClient, metadataSheetPath);
                        }
                    });
                }

                //add folder names to list of request names
                requestNames.AddRange(folders.Select(x => x.Prefix.Replace("/", "")));

            });

            return new ProteomicsStats
            {
                NumberOfRuns = numberOfFolders,
                NumberOfSamples = numberOfSamples,
                SizeInBytes = GetSize(containerClient, ""),
                RequestNames = JsonConvert.SerializeObject(requestNames)
            };
        }

        /// <summary>
        /// Collects NGS run statistics for the specified folder.
        /// </summary>
        /// <param name="accountName">The name of the proteomics storage account.</param>
        /// <param name="containerName">The name of the container to collect stats in.</param>
        /// <param name="prefix">The prefix of the folder path.</param>
        /// <returns>An instance of NgsRunStats</returns>
        internal NgsRunStats GetNgsRunStats(string containerName, string prefix)
        {
            var containerClient = blobServiceClient.GetBlobContainerClient(containerName);
            int folderCount = 0;

            IterateBlobPages(containerClient, prefix, (blobPage) =>
            {
                //if IsPrefix=true, we have a virtual folder
                var folders = blobPage.Values.Where(x => x.IsPrefix);
                folderCount += folders.Count();
            });

            return new NgsRunStats
            {
                NumberOfRuns = folderCount,
                SizeInBytes = GetSize(containerClient, prefix)
            };
        }

        /// <summary>
        /// Collects NGS sample statistics.
        /// </summary>
        /// <param name="accountName">The name of the proteomics storage account.</param>
        /// <param name="containerName">The name of the container to collect stats in.</param>
        /// <returns></returns>
        internal NgsSampleStats GetNgsSampleStats(string containerName)
        {
            var containerClient = blobServiceClient.GetBlobContainerClient(containerName);
            int folderCount = 0;

            var sampleNames = new List<string>();

            IterateBlobPages(containerClient, "", (blobPage) =>
            {
                //if IsPrefix=true, we have a virtual folder
                var folders = blobPage.Values.Where(x => x.IsPrefix);
                folderCount += folders.Count();

                sampleNames.AddRange(folders.Select(x => x.Prefix.Replace("/", "")));
            });

            return new NgsSampleStats
            {
                NumberOfSamples = folderCount,
                SizeInBytes = GetSize(containerClient, ""),
                SampleNames = JsonConvert.SerializeObject(sampleNames)
            };
        }

        /// <summary>
        /// Returns the total size of the blobs in the specified container.
        /// </summary>
        /// <param name="container">An instance of BlobContainerClient</param>
        /// <param name="prefix">The prefix of the folder path</param>
        /// <returns>The size in bytes.</returns>
        private long GetSize(BlobContainerClient container, string prefix)
        {
            long fileSize = 0;
            foreach (var blobItem in container.GetBlobs(prefix: prefix))
            {
                fileSize += blobItem.Properties.ContentLength.Value;
            }
            return fileSize;
        }
    }
}

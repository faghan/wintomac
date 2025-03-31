using System;
using Cfb.DataLakeStats.Helpers;

namespace Cfb.DataLakeStats
{
    public class Program
    {
        private static Guid PipelineRunId{ get; set; }

        private static void CollectProteomicsStats(BlobStorageHelper blobStorageHelper, DbHelper dbHelper, string containerName)
        {
            try
            {
                dbHelper.LogStart(PipelineRunId, "PROTEOMICS_RUNS");
                var stats = blobStorageHelper.GetProteomicsStats(containerName);
                int insertCount = dbHelper.WriteProteomicsStatsToTable(stats, PipelineRunId);
                dbHelper.LogFinish(PipelineRunId, "PROTEOMICS_RUNS", insertCount);
            }
            catch (Exception ex)
            {
                dbHelper.LogFinish(PipelineRunId, "PROTEOMICS_RUNS", 0, ex.Message);
                throw;
            }
        }

        private static void CollectNgsSamplesStats(BlobStorageHelper blobStorageHelper, DbHelper dbHelper, string containerName)
        {
            try
            {
                dbHelper.LogStart(PipelineRunId, "NGS_SAMPLES");
                var stats = blobStorageHelper.GetNgsSampleStats(containerName);
                int insertCount = dbHelper.WriteNgsSampleStatsToTable(stats, PipelineRunId);
                dbHelper.LogFinish(PipelineRunId, "NGS_SAMPLES", insertCount);
            }
            catch (Exception ex)
            {
                dbHelper.LogFinish(PipelineRunId, "NGS_SAMPLES", 0, ex.Message);
                throw;
            }
        }

        private static void CollectNgsRunStats(BlobStorageHelper blobStorageHelper, DbHelper dbHelper, string containerName, string prefix)
        {
            try
            {
                dbHelper.LogStart(PipelineRunId, "NGS_RUNS_" + containerName.ToUpper());
                var stats = blobStorageHelper.GetNgsRunStats(containerName, prefix);
                stats.SeqMachine = containerName;
                int insertCount = dbHelper.WriteNgsRunStatsToTable(stats, PipelineRunId);
                dbHelper.LogFinish(PipelineRunId, "NGS_RUNS_" + containerName.ToUpper(), insertCount);
            }
            catch (Exception ex)
            {
                dbHelper.LogFinish(PipelineRunId, "NGS_RUNS_" + containerName.ToUpper(), 0, ex.Message);
                throw;
            }
        }

        /// <summary>
        /// Writes the specified message to console prepending a timestamp.
        /// </summary>
        /// <param name="message">The message to write.</param>
        private static void WriteOut(string message)
        {
            Console.WriteLine("{0}: {1}", DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss.fff"), message);
        }
                
        /// <summary>
        /// Main entry point
        /// </summary>
        public static void Main()
        {
            // NB: This is needed to use the AsDataSet extension for ExcelDataReader
            // See https://github.com/ExcelDataReader/ExcelDataReader
            System.Text.Encoding.RegisterProvider(System.Text.CodePagesEncodingProvider.Instance);

            var dbHelper = new DbHelper(Environment.GetEnvironmentVariable("DWH_SERVER_NAME"),
                                        Environment.GetEnvironmentVariable("DWH_DB_NAME"),
                                        Environment.GetEnvironmentVariable("DWH_USER_NAME"),
                                        Environment.GetEnvironmentVariable("DWH_PASSWORD"));

            WriteOut("Start collecting stats...");

            PipelineRunId = Guid.NewGuid();

            var protBlobStorageHelper = new BlobStorageHelper(Environment.GetEnvironmentVariable("PROTEOMICS_ACCOUNT"));

            WriteOut("Collecting proteomics stats...");
            CollectProteomicsStats(protBlobStorageHelper,
                                   dbHelper,
                                   Environment.GetEnvironmentVariable("PROTEOMICS_CONTAINER"));
            WriteOut("Finished collecting proteomics stats");

            var ngsBlobStorageHelper = new BlobStorageHelper(Environment.GetEnvironmentVariable("NGS_ACCOUNT"));

            WriteOut("Collecting NGS samples stats...");
            CollectNgsSamplesStats(ngsBlobStorageHelper,
                                   dbHelper,
                                   Environment.GetEnvironmentVariable("NGS_SAMPLES_CONTAINER"));
            WriteOut("Finished collecting NGS samples stats");

            WriteOut("Collecting NGS run stats from NextSeqOutput...");
            CollectNgsRunStats(ngsBlobStorageHelper,
                               dbHelper,
                               Environment.GetEnvironmentVariable("NGS_NEXTSEQ_CONTAINER"),
                               "NextSeqOutput/");
            WriteOut("Finished collecting NGS run stats from NextSeqOutput");

            WriteOut("Collecting NGS run stats from MiSeqOutput...");
            CollectNgsRunStats(ngsBlobStorageHelper,
                               dbHelper,
                               Environment.GetEnvironmentVariable("NGS_MISEQ_CONTAINER"),
                               "MiSeqOutput/");
            WriteOut("Finished collecting NGS run stats from MiSeqOutput");

            WriteOut("Finisted collecting stats");
        }
    }
}

using DataLakeStats.Model;
using System;
using Npgsql;

namespace Cfb.DataLakeStats.Helpers
{
    /// <summary>
    /// Helper class for database operations.
    /// </summary>
    internal class DbHelper
    {
        private readonly string connectionString;

        internal DbHelper(string serverName, string databaseName, string userName, string password)
        {
            connectionString =
                string.Format(
                    "Server={0};Database={1};Username={2};Password={3};Port=5432;SSLMode=Prefer",
                    serverName,
                    databaseName,
                    userName,
                    password);
        }

        /// <summary>
        /// Returns an open PostgreSQL connection.
        /// </summary>
        private NpgsqlConnection GetConnection()
        {
            var connection = new NpgsqlConnection(connectionString);
            connection.Open();
            return connection;
        }

        /// <summary>
        /// Writes NGS run stats to database table.
        /// </summary>
        /// <param name="stats">An instance of NgsRunStats.</param>
        /// <param name="pipelineRunId">Run id from log.job.</param>
        /// <returns>Number of inserted rows.</returns>
        internal int WriteNgsRunStatsToTable(NgsRunStats stats, Guid pipelineRunId)
        {
            using var con = GetConnection();
            using var cmd = new NpgsqlCommand("INSERT INTO data_lake.ngs_run_stats " +
                "(collected_at, no_of_runs, data_volume_bytes, seq_machine, pipeline_run_id) " +
                "VALUES (@collected_at, @no_of_runs, @data_volume_bytes, @seq_machine, @pipeline_run_id)", con);
            cmd.Parameters.AddWithValue("@collected_at", DateTime.UtcNow);
            cmd.Parameters.AddWithValue("@no_of_runs", stats.NumberOfRuns);
            cmd.Parameters.AddWithValue("@data_volume_bytes", stats.SizeInBytes);
            cmd.Parameters.AddWithValue("@seq_machine", stats.SeqMachine);
            cmd.Parameters.AddWithValue("@pipeline_run_id", pipelineRunId);
            return cmd.ExecuteNonQuery();
        }

        /// <summary>
        /// Writes NGS sample stats to database table.
        /// </summary>
        /// <param name="stats">An instance of NgsSampleStats.</param>
        /// <param name="pipelineRunId">Run id from log.job.</param>
        /// /// <returns>Number of inserted rows.</returns>
        internal int WriteNgsSampleStatsToTable(NgsSampleStats stats, Guid pipelineRunId)
        {
            using var con = GetConnection();
            using var cmd = new NpgsqlCommand("INSERT INTO data_lake.ngs_sample_stats " +
                "(collected_at, no_of_samples, data_volume_bytes, sample_names, pipeline_run_id) " +
                "VALUES (@collected_at, @no_of_samples, @data_volume_bytes, @sample_names, @pipeline_run_id)", con);
            cmd.Parameters.AddWithValue("@collected_at", DateTime.UtcNow);
            cmd.Parameters.AddWithValue("@no_of_samples", stats.NumberOfSamples);
            cmd.Parameters.AddWithValue("@data_volume_bytes", stats.SizeInBytes);
            cmd.Parameters.AddWithValue("@sample_names", stats.SampleNames);
            cmd.Parameters.AddWithValue("@pipeline_run_id", pipelineRunId);
            return cmd.ExecuteNonQuery();
        }

        /// <summary>
        /// Writes proteomics stats to database table.
        /// </summary>
        /// <param name="stats">An instance of ProteomicsStats.</param>
        /// <param name="pipelineRunId">Run id from log.job.</param>
        /// <returns>Number of inserted rows.</returns>
        internal int WriteProteomicsStatsToTable(ProteomicsStats stats, Guid pipelineRunId)
        {
            using var con = GetConnection();
            using var cmd = new NpgsqlCommand("INSERT INTO data_lake.proteomics_stats " +
                "(collected_at, no_of_runs, no_of_samples, data_volume_bytes, request_names, pipeline_run_id) " +
                "VALUES (@collected_at, @no_of_runs, @no_of_samples, @data_volume_bytes, @request_names, @pipeline_run_id)", con);
            cmd.Parameters.AddWithValue("@collected_at", DateTime.UtcNow);
            cmd.Parameters.AddWithValue("@no_of_runs", stats.NumberOfRuns);
            cmd.Parameters.AddWithValue("@no_of_samples", stats.NumberOfSamples);
            cmd.Parameters.AddWithValue("@data_volume_bytes", stats.SizeInBytes);
            cmd.Parameters.AddWithValue("@request_names", stats.RequestNames);
            cmd.Parameters.AddWithValue("@pipeline_run_id", pipelineRunId);
            return cmd.ExecuteNonQuery();
        }

        /// <summary>
        /// Logs the start of a statistics collection operation.
        /// </summary>
        /// <param name="statsType">A string representing the type of statistics collection.</param>
        /// <param name="pipelineRunId">Run id from log.job.</param>        
        internal void LogStart(Guid pipelineRunId, string statsType)
        {
            using var con = GetConnection();
            using var cmd = new NpgsqlCommand("CALL log.job_begin(@p_pipeline_run_id, @p_pipeline_name, @p_job_name, @p_is_delta_load)", con);
            cmd.Parameters.AddWithValue("p_pipeline_run_id", pipelineRunId);
            cmd.Parameters.AddWithValue("p_pipeline_name", "collect-data-lake-stats");
            cmd.Parameters.AddWithValue("p_job_name", statsType);
            cmd.Parameters.AddWithValue("p_is_delta_load", false);
            cmd.ExecuteNonQuery();

        }

        /// <summary>
        /// Marks the operation as finished by setting status of the specified log entry.
        /// </summary>
        /// <param name="pipelineRunId">Run id from log.job.</param>
        /// <param name="status">Status: 2=finished, 3=failed.</param>
        internal void LogFinish(Guid pipelineRunId, string statsType, long? insertCount = null, string errorMessage = null)
        {
            using var con = GetConnection();
            if (errorMessage == null)
            {
                using var cmd = new NpgsqlCommand("CALL log.job_end(p_pipeline_run_id => @p_pipeline_run_id, p_job_name => @p_job_name, p_insert_count => @p_insert_count)", con);
                cmd.Parameters.AddWithValue("@p_pipeline_run_id", pipelineRunId);
                cmd.Parameters.AddWithValue("@p_job_name", statsType);
                cmd.Parameters.AddWithValue("@p_insert_count", insertCount);
                cmd.ExecuteNonQuery();
            }
            else
            {
                using var cmd = new NpgsqlCommand("CALL log.job_end(p_pipeline_run_id => @p_pipeline_run_id, p_job_name => @p_job_name, p_insert_count => @p_insert_count, p_error_message => @p_error_message)", con);
                cmd.Parameters.AddWithValue("@p_pipeline_run_id", pipelineRunId);
                cmd.Parameters.AddWithValue("@p_job_name", statsType);
                cmd.Parameters.AddWithValue("@p_insert_count", insertCount);
                cmd.Parameters.AddWithValue("@p_error_message", errorMessage);
                cmd.ExecuteNonQuery();
            }
        }
    }
}

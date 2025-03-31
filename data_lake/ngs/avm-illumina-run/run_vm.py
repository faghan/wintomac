# -*- coding: utf-8 -*-

"""
VM script for converting/placing Illumina NGS output, as well as running
analysis.

Requires certain environment variables to be set for operation:
  - run_path : eg: "/nextseq01/NextSeqOutput/XYZ123". Full path should
    be mounted for the container and "XYZ123" would be the run_id to be used.
    Type of run (MiSeq or NextSeq) will be gathered from this path.
  - sample_path: eg: "/samples". Full path should be mounted for the
    container and reads for each sample will be put under here.
    (eg: /samples/abc1/reads/read_1.fastq.gz)
  - snakefile_path : path to snakefile / rnaseq pipeline.
  - reference_table : path to file matching reference IDs with files.
  - vm_log : path to report completion of pipeline runs to be used for vm
    shutdown.

Also requires a managed (or system) identity and necessary access policy to get
secret from keyvault for data warehouse.

Overall function:
 - NextSeq runs will be put through bcl2fastq conversion.
   - A library sheet name "SampleSheet.csv" is expected in run path. This will
   be converted to a usable sample sheet for bcl2fastq.
 - Miseq runs will only get the reads placed in proper sample folder structure.
 - Once the read files are distributed, a flag file (sample.ready) will be
   placed in the root folder of specific sample. This can be used to initiate
   analysis pipelines.
"""

import sys
import re
import logging
import yaml
import pyodbc
import pymsteams
import json
from subprocess import Popen, PIPE, check_output
from datetime import datetime
from os import environ, makedirs, getcwd, chdir
from os.path import basename, join, exists
from glob import glob
from shutil import copy
from typing import Union


def library_to_samplesheet(run_path: str) -> int:
    """
    Converts library sheet to sample sheet.

    :param run_path: path to sequencing run files.
    :return: 0 for successful execution and "returncode" for failed execution.
    """
    logging.info('Converting library sheet to sample sheet for NextSeq run.')
    process = Popen(['library_to_samplesheet',
                     '--run_parameters', f'{run_path}/RunParameters.xml',
                     '--library_sheet', f'{run_path}/SampleSheet.csv',
                     '--output', f'{run_path}/SampleSheet_ready.csv',
                     ],
                    stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()

    with open(f'{run_path}/lib2ss.out', 'w') as outfile:
        outfile.writelines(stdout.decode())
    with open(f'{run_path}/lib2ss.err', 'w') as errfile:
        errfile.writelines(stderr.decode())
    logging.info(
        f'Library to samplesheet stdout and stderr are written to '
        f'{run_path}/lib2ss.out and {run_path}/lib2ss.err respectively.')

    if process.returncode == 0:
        logging.info('Library to samplesheet conversion finished successfully.')
        return 0
    else:
        logging.error(f'Library to sample sheet failed with return code '
                      f'{process.returncode}.\n'
                      f'Error message:\n{stderr}')
        return process.returncode


def bcl2fastq(run_path: str) -> int:
    """
    Runs bcl2fastq to generate fastq files from raw run output.

    :param run_path: path to sequencing run files.
    :return: 0 for successful execution and "returncode" for failed execution.
    """

    logging.info('Beginning bcl2fastq conversion.')
    process = Popen(['bcl2fastq',
                     '--runfolder-dir', f'{run_path}',
                     '--sample-sheet', f'{run_path}/SampleSheet_ready.csv',
                     '--processing-threads', '8',
                     '--loading-threads', '4',
                     '--writing-threads', '4',
                     ],
                    stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()

    # write stdout and strerr to files
    with open(f'{run_path}/bcl2fastq.out', 'w') as outfile:
        outfile.writelines(stdout.decode())
    with open(f'{run_path}/bcl2fastq.err', 'w') as errfile:
        errfile.writelines(stderr.decode())
    logging.info(
        f'bcl2fastq stdout and stderr are written to '
        f'{run_path}/bcl2fastq.out and {run_path}/bcl2fastq.err respectively.')

    if process.returncode == 0:
        logging.info('bcl2fastq finished successfully.')
        return 0
    else:
        logging.error(f'bcl2fastq failed with return code '
                      f'{process.returncode}.\n'
                      f'Error message:\n{stderr}')
        return process.returncode


def generate_reports(run_path: str, run_type: str) -> int:
    """
    Runs ngs_reports to generate reports, update dashboard.

    :param run_path: path to sequencing run files.
    :param run_path: "NextSeq" or "MiSeq".
    :return: 0 for successful execution and "returncode" for failed execution.
    """

    logging.info('Beginning NGS report generation.')
    if run_type == 'NextSeq':
        cache_path = '/nextseq01/NextSeqReportsCache'
    elif run_type == 'MiSeq':
        cache_path = '/miseq01/MiSeqReportsCache'
    else:  # Should be able to reach here anyway.
        logging.error(f'Run_type must be one of NextSeq or MiSeq. Unrecognised '
                      f'type: {run_type}')
        return -1

    logging.info('Retrieving email details for report notification.')
    smtp_user = get_secret_from_key_vault('cfb-ngs-keyvault',
                                          'ngs-reports-smtp-user')
    smtp_password = get_secret_from_key_vault('cfb-ngs-keyvault',
                                              'ngs-reports-smtp-password')
    smtp_recipient = get_secret_from_key_vault('cfb-ngs-keyvault',
                                               'ngs-reports-smtp-recipient')

    if None in [smtp_user, smtp_password, smtp_recipient]:
        logging.error(f'One or more SMTP details could not be retrieved from '
                      f'keyvault.')
        return -1

    process = Popen(['ngs_reports', 'all',
                     '--instrument', run_type,
                     '--cache', cache_path,
                     '--run', run_path,
                     '--output', f'{run_path}/Reports',
                     '--smtp-username', smtp_user,
                     '--smtp-password', smtp_password,
                     '--smtp-host', 'mail.dtu.dk',
                     '--smtp-port', '587',
                     '--smtp-recipient', smtp_recipient
                     ],
                    stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()

    # write stdout and strerr to files
    with open(f'{run_path}/ngsreport.out', 'a') as outfile:
        outfile.writelines(stdout.decode())
    with open(f'{run_path}/ngsreport.err', 'a') as errfile:
        errfile.writelines(stderr.decode())
    logging.info(
        f'ngs_reports stdout and stderr are written to '
        f'{run_path}/ngsreport.out and {run_path}/ngsreport.err respectively.')

    if process.returncode == 0:
        logging.info(f'ngs_reports finished successfully.')
        return 0
    else:
        logging.error(f'ngs_reports failed with return code '
                      f'{process.returncode}.\n'
                      f'Error message:\n{stderr}')
        return process.returncode


def generate_samples_to_files(run_path: str) -> dict:
    """
    Find fastq files under run_path and collect sample vs files in a dictionary.

    :param run_path: path to sequencing run files.
    :return: dictionary in the form of
    {'sample_01': '/path/to/file/sample.fastq.gz, ...}
    """

    logging.info('Matching samples with read files.')
    # regular expression to select the reads files and extract sample names.
    p = re.compile(
        '^(.*)(_S[0-9]+)(_L00[1-4])(_R[12])(_[0-9]{3}[\S]*\.fastq\.gz)$')
    samples_to_files = dict()
    for file in glob(f'{run_path}/**/*.gz', recursive=True):
        fastq = basename(file)
        pm = p.match(fastq)

        if pm:
            sample = pm.group(1)
            # Ignore undetermined reads
            if sample == "Undetermined":
                continue
            elif sample in samples_to_files:
                samples_to_files[sample].append(file)
            else:
                samples_to_files[sample] = [file]

    return samples_to_files


def copy_reads_to_destination(sample_path: str,
                              samples_to_files: dict, ) -> list:
    """
    Copies read files to sample volume (and collects non unique sample ids).

    :param sample_path: path to samples volume.
    :param samples_to_files: A dictionary matching sample ids with read files.
    :return: A list of new sample IDs
    """

    logging.info('Copying reads to sample path.')
    used_sample_ids = list()
    new_sample_ids = list()
    for sample, files in samples_to_files.items():
        full_sample_path = join(sample_path, sample)
        # check if sample id is already used
        if exists(full_sample_path):
            used_sample_ids.append(sample)
            continue
        else:
            new_sample_ids.append(sample)
            full_read_path = join(full_sample_path, 'reads', 'fastq')
            makedirs(full_read_path)
            for file in files:
                copy(file, full_read_path)
            with open(join(full_sample_path,
                           f'{sample}.ready'),
                      'w+') as ready_file:
                ready_file.write(run_id)

    # finish and report:
    if len(used_sample_ids) == 0:
        logging.info('All sample IDs are unique with respect to previous runs.')
    else:
        logging.warning('Run contains samples with previously used IDs:\n',
                        '\n'.join(
                            [sample for sample in sorted(used_sample_ids)]),
                        '\nReads from these are left in run path.')
    return new_sample_ids


def get_secret_from_key_vault(vault_name: str,
                              secret_name: str) -> Union[str, None]:
    """
    Retrieves a secret value from key vault.

    :param vault_name: Azure key vault name
    :param secret_name: secret name in Azure key vault
    :return: secret in string form or None if can't be retrieved.
    """

    logging.info(f'Retrieving {secret_name} from {vault_name} keyvault.')
    process = Popen(['az', 'keyvault', 'secret', 'show',
                     '--vault-name', vault_name,
                     '--name', secret_name,
                     '--output', 'json'],
                     stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()

    if process.returncode == 0:
        logging.info(f'{secret_name} retrieved from keyvault.')
        return json.loads(stdout)['value']
    else:
        logging.error(f'Failed to retrieve {secret_name}. Exit code:\n'
                      f'{process.returncode}\n{stderr}')
        return None


def get_sample_details(sample: str, ) -> Union[pyodbc.Row, None]:
    """
    Retrieves reference ID from data warehouse for a given sample.

    :param sample: sample ID
    :return: A pyodbc.Row with matching reference ID and nucleic acid type or
    None if not found.
    """

    connection_string = get_secret_from_key_vault('cfb-ngs-keyvault',
                                                  'dwh-connection-string')
    if connection_string is None:
        logging.error(f'Failed to retrieve connection string. Exiting.')
        raise

    conn = None
    try:
        sql = '''
              SELECT rg.name, sss.nucleotide_type
              FROM lims.sequencing_submission_sample sss
                  LEFT OUTER JOIN lims.strain s ON sss.strain = s.name
                  LEFT OUTER JOIN lims.reference_genome rg ON s.reference_genome = rg.name
              WHERE sss.name = ?;              
              '''
        conn = pyodbc.connect(connection_string, autocommit=True)
        cur = conn.cursor()
        cur.execute(sql, sample)
        row = cur.fetchone()
        cur.close()

        return row
        # This should return a pyodbc.row if the sample is registered and
        # None otherwise.

    except Exception as e:
        logging.exception(
            'Exception occurred retrieving details for sample:\n' +
            str(e))
        raise
    finally:
        if conn is not None:
            conn.close()


def run_rnaseq_analysis(sample: str,
                        reference_genome: str,
                        snakefile_path: str,
                        sample_path: str,
                        reference_table: str,
                        ) -> int:
    '''
    Runs RNAseq analysis pipeline for a given sample. Results of the workflow
    would be placed in sample path.

    :param sample: sample name/id
    :param reference_genome: reference genome for read alignment. Needs to be in
                             reference genomes table.
    :param snakefile_path: path to snakefile where analysis pipeline is
                           implemented.
    :param sample_path: path for to sample analysis
    :param reference_table: a yaml file with records of genomes and respective sequence,
                            annotation files.

    :return: 0 for successful execution, return code for failed run.

    '''

    logging.info(f'Beginning RNAseq analysis for {sample}.')

    logging.info(f'Retrieving git head for pipeline...')
    pwd = getcwd()
    chdir(snakefile_path)
    git_head = check_output(['git',
                             'rev-parse',
                             '--short',
                             'HEAD']).decode().strip()
    chdir(pwd)
    logging.info(f'Pipeline at {git_head}.')

    results_path = join(sample_path,
                        sample,
                        'rnaseq',
                        f'{reference_genome}_{git_head}')
    raw_read_path = join(sample_path, sample, 'reads')
    process = Popen(['snakemake',
                     'all',
                     '--snakefile', join(snakefile_path, 'Snakefile'),
                     '--configfile', join(snakefile_path, 'config.yaml'),
                     '--directory', results_path,
                     '--config', f'sample_id={sample}',
                     f'raw_read_path={raw_read_path}',
                     f'reference_id={reference_genome}',
                     f'reference_table={reference_table}',
                     '--use-conda',
                     '--conda-prefix', '/home/avmillumina/miniconda3/envs',
                     '--cores', '8'
                     ],
                    stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()

    # write stdout and strerr to files
    with open(f'{results_path}/rnaseq.out', 'w') as outfile:
        outfile.writelines(stdout.decode())
    with open(f'{results_path}/rnaseq.err', 'w') as errfile:
        errfile.writelines(stderr.decode())
    logging.info(
        f'RNAseq analysis stdout and stderr are written to '
        f'{results_path}/rnaseq.out and {results_path}/rnaseq.err respectively.'
    )

    if process.returncode == 0:
        logging.info('RNAseq analysis finished successfully.')
        open(join(results_path, 'analysis.ready'), 'w').close()
        return 0
    else:
        logging.error(f'RNAseq analysis failed with return code '
                      f'{process.returncode}.\n'
                      f'Error message:\n{stderr}')
        return process.returncode


def send_msteams_message(message: str, msteams_webhook: str) -> None:
    """
    Sends MS Teams message to Infrastructure notification channel.

    :param message: message to send
    :param msteams_webhook: webhook for the teams channel
    :return: None
    """

    myTeamsMessage = pymsteams.connectorcard(msteams_webhook)
    myTeamsMessage.text(message)
    myTeamsMessage.send()

    return


if __name__ == '__main__':

    # just to catch a general error here and update the vm.log for vm stop
    # function app.
    try:
        # get msteams webhook from key vault
        msteams_webhook = get_secret_from_key_vault('cfb-ngs-keyvault',
                                                    'msteams-ngs-pipeline-notifications-webhook')

        # get necessary details
        run_path = environ['run_path']
        run_id = basename(run_path)
        nextseq = True if 'nextseq' in run_path else False
        sample_path = environ['sample_path']
        snakefile_path = environ['snakefile_path']
        reference_table = environ['reference_table']
        vm_log = environ['vm_log']

        # get a list of validated references for checking against sample
        # references.
        with open(reference_table, 'r') as file:
            valid_references = yaml.load(file, yaml.FullLoader).keys()

        # check if log file exists. If it does, Leave without doing anything.
        log_file = join(run_path, 'vm.log')
        if exists(log_file):
            print(f'There is a log file for this run:\n{log_file}\n'
                  'If you want to run the analysis regardless, delete/rename log '
                  'file and run again.'
                  'Note that this will run bcl2fastq and copying of reads to '
                  'samples path part, but not necessarily the RNAseq analysis part.'
                  )
            send_msteams_message(
                f'Pipeline for run ID {run_id} failed due to previous execution.',
                msteams_webhook)
            with open(vm_log, 'a') as vm_log_file:
                vm_log_file.write(f'{str(datetime.now())}\n'
                                  f'\tPipeline for run ID {run_id} failed due '
                                  f'to previous execution.\n\n')
            sys.exit(-1)

        logging.basicConfig(filename=log_file,
                            filemode='w',
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            level=logging.DEBUG)

        logging.info(f'Processing run: {run_id}')

        if nextseq:
            logging.info('NextSeq run will be processed.')

            lib2ss_return = library_to_samplesheet(run_path)
            if lib2ss_return != 0:
                logging.info('Terminated run processing due to error.')
                send_msteams_message(
                    f'Pipeline for run ID {run_id} failed at library sheet conversion step.',
                    msteams_webhook)
                with open(vm_log, 'a') as vm_log_file:
                    vm_log_file.write(f'{str(datetime.now())}\n'
                                      f'\tPipeline for run ID {run_id} failed at library '
                                      'sheet conversion step.\n\n')
                sys.exit(-1)

            bcl2fastq_return = bcl2fastq(run_path)
            if bcl2fastq_return != 0:
                logging.info('Terminated run processing due to error.')
                send_msteams_message(
                    f'Pipeline for run ID {run_id} failed at bcl2fastq conversion step.',
                    msteams_webhook)
                with open(vm_log, 'a') as vm_log_file:
                    vm_log_file.write(f'{str(datetime.now())}\n'
                                      f'\tPipeline for run ID {run_id} failed at bcl2fastq '
                                      'conversion step.\n\n')
                sys.exit(-1)

        else:
            # nothing to do for miseq as fastq files are generated by the
            # sequencer
            logging.info('MiSeq run will be processed.')

        # Generate reports
        logging.info(f'Generating reports for {run_id}.')
        report_return = generate_reports(run_path=run_path,
                                         run_type='NextSeq' if nextseq else 'MiSeq')
        if report_return != 0:
            logging.error(f'ngs_reports failed with '
                          f'return code: {report_return}')
            send_msteams_message(f'ngs_reports failed.',
                                 msteams_webhook)
            # No need to terminate run as this is not a critical step.

        samples_to_files = generate_samples_to_files(run_path)
        new_sample_ids = copy_reads_to_destination(sample_path,
                                                   samples_to_files)

        if len(new_sample_ids) == 0:
            logging.info('No new sample ids found. Finishing process.')

        else:
            for sample in new_sample_ids:
                sample_details = get_sample_details(sample)

                # Handle unregistered samples
                if sample_details is None:
                    logging.info(f'{sample} is not registered.')
                    continue
                else:
                    reference_genome, nucleic_acid_type = sample_details

                # Deal with RNAseq with valid reference
                if (nucleic_acid_type in ['Total RNA',
                                          'Messenger RNA (mRNA)']) \
                   and \
                   (reference_genome in valid_references):
                    logging.info(
                        f'RNAseq sample {sample} is matched with {reference_genome}.')
                    rnaseq_out = run_rnaseq_analysis(sample,
                                                     reference_genome,
                                                     snakefile_path,
                                                     sample_path,
                                                     reference_table)

                # Deal with RNAseq without valid reference
                elif (nucleic_acid_type in ['Total RNA',
                                            'Messenger RNA (mRNA)']) \
                   and \
                   (reference_genome not in valid_references):
                    logging.info(
                        f'Reference genome for RNAseq sample {sample} is not '
                        f'found in references table. Skipping sample '
                        f'processing.')
                    send_msteams_message(f'RNAseq sample {sample} could not be '
                                         f'processed as {reference_genome} is '
                                         f'not in valid references.',
                                         msteams_webhook)

                # Deal with non RNAseq samples
                elif (nucleic_acid_type not in ['Total RNA',
                                                'Messenger RNA (mRNA)']):
                    logging.info(f'Sample {sample} is not for RNAseq. No '
                                 f'analysis defined.')

                # Nothing should go here
                else:
                    logging.info(
                        f'Something weird happened with {sample} and'
                        f' {reference_genome}.')
                    send_msteams_message(f'Something weird happened with '
                                         f'{sample} and {reference_genome}.',
                                         msteams_webhook)

    except Exception as e:
        logging.error(str(e))
        send_msteams_message(
            f'Pipeline for run ID {run_id} failed with unhandeled exception.',
            msteams_webhook)
        with open(vm_log, 'a') as vm_log_file:
            vm_log_file.write(f'{str(datetime.now())}\n'
                              f'\tPipeline for run ID {run_id} failed with '
                              f'unhandeled exception:\n'
                              f'{str(e)}\n\n')
            sys.exit(-1)

    logging.info('Done')
    with open(vm_log, 'a') as vm_log_file:
        vm_log_file.write(f'{str(datetime.now())}\n'
                          f'\tPipeline for run ID {run_id} completed.\n\n')
    sys.exit(0)

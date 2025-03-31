import logging

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models
from django.forms.models import model_to_dict

from rest_framework import exceptions


class DataWarehouseManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().using("datawarehouse")


class DataWarehouseModel(models.Model):
    objects = DataWarehouseManager()

    class Meta:
        abstract = True
        managed = False


class BenchlingUser(AbstractBaseUser):
    objects = DataWarehouseManager()

    class Meta:
        managed = False
        db_table = 'biosustain\".\"user$raw'

    # dw_id = models.IntegerField(primary_key=True)

    id = models.TextField(primary_key=True)
    handle = models.TextField(unique=True)
    name = models.TextField()
    email = models.TextField()

    password = None
    last_login = None

    @property
    def is_active(self):
        return not self.is_suspended

    is_suspended = models.BooleanField(db_column="is_suspended")

    @property
    def username(self):
        #return f"{self.handle}@dtu.dk"
        return f"{self.handle}"

    USERNAME_FIELD = "handle"
    EMAIL_FIELD = "email"


class DataLakeKey(DataWarehouseModel):
    class Meta:
        db_table = 'acl\".\"user_data_lake_key'

    username = models.TextField(primary_key=True)

    @classmethod
    def get_username(cls, api_key):
        for row in cls.objects.raw(
            "SELECT username FROM acl.username_by_data_lake_key(%s)", [api_key],
        ):
            return row.username


class DataBrokerLog(DataWarehouseModel):
    class Meta:
        db_table = 'log\".\"data_broker'

    requested_at = models.DateTimeField()
    api_endpoint = models.TextField(null=True)
    arguments = models.TextField(null=True)
    ip_address = models.TextField()
    username = models.TextField(null=True)
    api_key = models.TextField()
    http_response = models.IntegerField()
    response_info = models.TextField(null=True)
    response_at = models.DateTimeField()

    def set_response_info_from_exception(self, error):
        message = str(error)
        self.response_info = message

    def save(self, *args, **kwargs):
        if not settings.AZURE_DWH_LOGGING:
            log = logging.getLogger(__name__)
            log.warning("event not logged to dwh: %s", model_to_dict(self))
            return

        kwargs.setdefault("using", "datawarehouse")

        super().save(*args, **kwargs)


class LimsRawSequencingSubmissionSample(DataWarehouseModel):
    class Meta:
        db_table = 'biosustain\".\"sequencing_submission_sample$raw'

    id = models.TextField(primary_key=True)
    created_at = models.DateTimeField(db_column="created_at$")
    dw_creator = models.ForeignKey(
        BenchlingUser, on_delete=models.CASCADE, db_column="creator_id$", to_field="id",
    )
    source_id = models.TextField()
    name = models.TextField(db_column="name$")
    modified_at = models.DateTimeField(db_column="modified_at$")
    entity_registry_id = models.TextField(null=True, db_column="file_registry_id$")
    is_archived = models.BooleanField(db_column="archived$")
    archive_reason = models.TextField(null=True, db_column="archive_purpose$")
    url = models.TextField(db_column="url$")
    antibody_if_chip_seq = models.TextField(null=True)
    average_size_of_customer_made_library_in_bp = models.IntegerField(null=True)
    biological_replicate = models.IntegerField(null=True)
    buffer = models.TextField(null=True)
    cell_line = models.TextField(null=True)
    comments = models.TextField(null=True)
    concentration_ngul = models.FloatField(null=True)
    experiment = models.TextField(null=True)
    nucleotide_type = models.TextField(null=True)
    organism = models.TextField(null=True)
    organism_if_external = models.TextField(null=True)
    parent_culture = models.TextField(null=True)
    rinrqn_if_rna = models.FloatField(null=True)
    strain = models.TextField(null=True)
    technical_replicate = models.IntegerField(null=True)
    volume_ul = models.FloatField(null=True)

    @classmethod
    def check_user_access(cls, user, name):
        if not cls.objects.raw(
            """
            SELECT s.id
            FROM biosustain.sequencing_submission_sample$raw s
                JOIN acl.user_source us
                    ON us.source_id = s.source_id
            WHERE s.name$ = %s
                AND us."user" = %s
            LIMIT 1
            """,
            [name, user.username],
        ):
            # do not differentiate between sample not found and no permissions; this
            # is to avoid leaking information about samples in the database/storage
            raise exceptions.PermissionDenied()


class LimsRawAcProteomics(DataWarehouseModel):
    class Meta:
        db_table = 'biosustain\".\"ac_proteomics$raw'

    id = models.TextField(primary_key=True)
    created_at = models.DateTimeField(null=True, db_column="created_at$")
    request_status = models.TextField(null=True, db_column="status$")
    name = models.TextField(null=True, db_column="display_id$")
    url = models.TextField(null=True, db_column="url$")
    expected_delivery_date = models.DateField(null=True)
    expected_number_of_samples = models.IntegerField(null=True)
    comments = models.TextField(null=True)
    scheduled_on = models.DateField(null=True, db_column="scheduled_on$")
    comments_fulfiller = models.TextField(null=True)
    dw_creator = models.ForeignKey(
        BenchlingUser, on_delete=models.CASCADE, db_column="creator_id$", to_field="id", related_name="+",
    )
    dw_requestor = models.ForeignKey(
        BenchlingUser, on_delete=models.CASCADE, db_column="requestor_id$", to_field="id", related_name="+",
    )

    analytical_submission_samples = models.ManyToManyField(
        "LimsRawAnalyticalSubmissionSample",
        related_name="+",
        related_query_name="+",
        through="LimsRawRelAcProteomicsAnalyticalSubmissionSample",
        through_fields=("ac_proteomics", "analytical_submission_sample"),
    )

    proteomics_submission_samples = models.ManyToManyField(
        "LimsRawProteomicsSubmissionSample",
        related_name="+",
        related_query_name="+",
        through="LimsRawRelAcProteomicsProteomicsSubmissionSample",
        through_fields=("ac_proteomics", "proteomics_submission_sample"),
    )

    @classmethod
    def check_user_access(cls, user, name):
        if not cls.objects.raw(
            """
            SELECT s.id
            FROM biosustain.ac_proteomics$raw s
                JOIN acl.user_source us
                    ON us.source_id = s.source_id
            WHERE s.display_id$ = %s
                AND us."user" = %s
            LIMIT 1
            """,
            [name, user.username],
        ):
            # do not differentiate between sample not found and no permissions; this
            # is to avoid leaking information about samples in the database/storage
            raise exceptions.PermissionDenied()


class LimsRawProteomicsSubmissionSample(DataWarehouseModel):
    class Meta:
        db_table = 'biosustain\".\"proteomics_submission_sample$raw'

    id = models.TextField(primary_key=True)
    created_at = models.DateTimeField(db_column="created_at$")
    dw_creator = models.ForeignKey(
        BenchlingUser, on_delete=models.CASCADE, db_column="creator_id$", to_field="id", related_name="+",
    )
    source_id = models.TextField()
    name = models.TextField(db_column="name$")
    modified_at = models.DateTimeField(db_column="modified_at$")
    entity_registry_id = models.TextField(null=True, db_column="file_registry_id$")
    is_archived = models.BooleanField(db_column="archived$")
    archive_reason = models.TextField(null=True, db_column="archive_purpose$")
    url = models.TextField(db_column="url$")
    biological_replicate = models.IntegerField(null=True)
    cell_line = models.TextField(null=True)
    cho_culture = models.TextField(null=True)
    comments = models.TextField(null=True)
    experiment = models.TextField(null=True)
    fermentation_culture = models.TextField(null=True)
    heterologous_proteins = models.TextField(null=True)
    sample_density = models.FloatField(null=True)
    sample_density_type = models.TextField(null=True)
    strain = models.TextField(null=True)
    technical_replicate = models.IntegerField(null=True)


class LimsRawRelAcProteomicsProteomicsSubmissionSample(DataWarehouseModel):
    class Meta:
        db_table = 'biosustain\".\"request_sample'

    ac_proteomics = models.ForeignKey(
        LimsRawAcProteomics, on_delete=models.CASCADE, db_column="request_id", to_field="id",
    )
    proteomics_submission_sample = models.ForeignKey(
        LimsRawProteomicsSubmissionSample, on_delete=models.CASCADE, db_column="entity_id", to_field="id",
    )


class LimsRawAnalyticalSubmissionSample(DataWarehouseModel):
    class Meta:
        db_table = 'biosustain\".\"analytical_submission_sample$raw'

    id = models.TextField(primary_key=True)
    created_at = models.DateTimeField(db_column="created_at$")
    dw_creator = models.ForeignKey(
        BenchlingUser, on_delete=models.CASCADE, db_column="creator_id$", to_field="id", related_name="+",
    )
    source_id = models.TextField()
    name = models.TextField(db_column="name$")
    modified_at = models.DateTimeField(db_column="modified_at$")
    entity_registry_id = models.TextField(null=True, db_column="file_registry_id$")
    is_archived = models.BooleanField(db_column="archived$")
    archive_reason = models.TextField(null=True, db_column="archive_purpose$")
    url = models.TextField(db_column="url$")
    age_of_inoculum_at_inoculation_h = models.FloatField(null=True)
    analysis_type = models.TextField(null=True)
    buffer_if_purified_protein = models.TextField(null=True)
    cell_count_if_cell_pellet = models.FloatField(null=True)
    cell_line = models.TextField(null=True)
    cellular_compartment = models.TextField(null=True)
    comments = models.TextField(null=True)
    cultivation_container_idposition = models.TextField(null=True)
    cultivation_details = models.TextField(null=True)
    dilution_factor = models.IntegerField(null=True)
    experiment = models.TextField(null=True)
    flask_if_ale = models.IntegerField(null=True, db_column="flask_if_ale")
    freeze_dried = models.TextField(null=True)
    medium_new = models.TextField(null=True)
    medium_name_if_external = models.TextField(null=True)
    operator_name = models.TextField(null=True)
    osmolality_mmolkg = models.FloatField(null=True)
    parent_culture = models.TextField(null=True)
    passage_number = models.IntegerField(null=True)
    ph_of_culture = models.FloatField(null=True)
    preculture_details = models.TextField(null=True)
    protein_concentration_if_purified_protein = models.TextField(
        null=True
    )
    replicate = models.IntegerField(null=True)
    sample_prep_date = models.DateField(null=True)
    sample_prep_sopversion = models.TextField(null=True)
    sample_type = models.TextField(null=True)
    shaker_or_stirrer_speed_rpm = models.FloatField(null=True)
    shaking_diameter_mm = models.FloatField(null=True)
    shaking_mode = models.TextField(null=True)
    solvent = models.TextField(null=True)
    strain = models.TextField(null=True)
    strain_cell_line_or_organism_name_if_external = models.TextField(
        null=True
    )
    strain_clone = models.TextField(null=True)
    temperature_c = models.FloatField(null=True)
    timepoint_h = models.FloatField(null=True)
    timepoint_sample = models.TextField(null=True)


class LimsRawRelAcProteomicsAnalyticalSubmissionSample(DataWarehouseModel):
    class Meta:
        db_table = 'biosustain\".\"request_sample$raw'

    ac_proteomics = models.ForeignKey(
        LimsRawAcProteomics, on_delete=models.CASCADE, db_column="request_id", to_field="id",
    )
    analytical_submission_sample = models.ForeignKey(
        LimsRawAnalyticalSubmissionSample, on_delete=models.CASCADE, db_column="entity_id", to_field="id",
    )

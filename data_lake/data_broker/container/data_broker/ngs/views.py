from pathlib import PurePosixPath

from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import APIView

from .azure import get_blob_sas_url, get_container_client

from data_broker.common.views import ListFilesBase, DownloadFileBase

from data_broker.data_warehouse.models import LimsRawSequencingSubmissionSample
from data_broker.data_warehouse.serializers import (
    LimsRawSequencingSubmissionSampleSerializer,
)
from data_broker.data_warehouse.logging import log_api_endpoint


class ListSamplesView(APIView):
    @log_api_endpoint("ngs:samples")
    def get(self, request, format=None):
        if not request.user.is_authenticated:
            raise AssertionError("user is not authenticated")

        samples = self.query_samples(request).prefetch_related("dw_creator")

        return Response(
            LimsRawSequencingSubmissionSampleSerializer(
                samples, context={"request": request}, many=True
            ).data
        )

    @classmethod
    def query_samples(cls, request):
        query = [
            """
            SELECT s.*
            FROM biosustain.sequencing_submission_sample$raw s
                JOIN acl.user_source us
                    ON us.source_id = s.source_id
            WHERE us."user" = %s"""
        ]

        # Archived samples are hidden by default
        if not _get_toggle_param(request, "archived", default=False):
            query.append("AND s.archived$ = FALSE")

        return LimsRawSequencingSubmissionSample.objects.raw(
            "\n".join(query), [request.user.username],
        )


class ListFilesView(ListFilesBase):
    namespace = "ngs"
    list_view = ListSamplesView
    list_model = LimsRawSequencingSubmissionSample
    get_container_client = staticmethod(get_container_client)

    @log_api_endpoint("ngs:files")
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)


class DownloadFileView(DownloadFileBase):
    list_model = LimsRawSequencingSubmissionSample

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_sas_url = get_blob_sas_url

    @log_api_endpoint("ngs:download")
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)


def _split_blob_path(blob):
    blob = PurePosixPath(blob)
    blob_parts = blob.parts
    if not blob_parts or ".." in blob_parts:
        # disallow tomfoolery
        raise exceptions.ValidationError("invalid path")

    return blob, blob_parts


def _get_toggle_param(request, name, default):
    value = request.query_params.get(name)
    if value is None:
        return default

    return value.lower() in ("1", "true", "yes")

from rest_framework.response import Response
from rest_framework.views import APIView

from .azure import get_blob_sas_url, get_container_client

from data_broker.common.views import ListFilesBase, DownloadFileBase

from data_broker.data_warehouse.models import LimsRawAcProteomics
from data_broker.data_warehouse.serializers import LimsRawAcProteomicsSerializer
from data_broker.data_warehouse.logging import log_api_endpoint


class ListRequestsView(APIView):
    @log_api_endpoint("proteomics:requests")
    def get(self, request, format=None):
        if not request.user.is_authenticated:
            raise AssertionError("user is not authenticated")

        samples = self.query_samples(request).prefetch_related(
            "dw_creator",
            "dw_requestor",
            "analytical_submission_samples",
            "analytical_submission_samples__dw_creator",
            "proteomics_submission_samples",
            "proteomics_submission_samples__dw_creator",
        )

        return Response(
            LimsRawAcProteomicsSerializer(
                samples, context={"request": request}, many=True
            ).data
        )

    @classmethod
    def query_samples(cls, request):
        query = """
            SELECT p.*
            FROM biosustain.ac_proteomics$raw p
                JOIN acl.user_source us
                    ON us.source_id = p.source_id
            WHERE us."user" = %s
        """

        return LimsRawAcProteomics.objects.raw(query, [request.user.username],)


class ListFilesView(ListFilesBase):
    namespace = "proteomics"
    list_view = ListRequestsView
    list_model = LimsRawAcProteomics
    get_container_client = staticmethod(get_container_client)

    @log_api_endpoint("proteomics:files")
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)


class DownloadFileView(DownloadFileBase):
    list_model = LimsRawAcProteomics

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_sas_url = get_blob_sas_url

    @log_api_endpoint("proteomics:download")
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

import json

from pathlib import PurePosixPath

from azure.storage.blob import BlobPrefix

from django.http import HttpResponse, HttpResponseRedirect

from rest_framework.exceptions import (
    APIException,
    NotFound,
    ParseError,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView


class ListFilesBase(APIView):
    namespace = None
    list_view = None
    list_model = None
    get_container_client = None

    def get(self, request, blob="", format=None):
        if not request.user.is_authenticated:
            raise AssertionError("user is not authenticated")

        if blob in ("", "/"):
            # List only those folders corresponding to accessible samples
            return self._list_root_folders(request)

        blob, blob_parts = _split_blob_path(blob)

        # verify that the current user can access the sample
        self.list_model.check_user_access(user=request.user, name=blob_parts[0])

        blobs = []
        candidate_blobs = []
        prefixes = set()
        client = self.get_container_client()
        for item in client.walk_blobs(name_starts_with=f"{blob.as_posix()}/"):
            name = PurePosixPath(item["name"]).name

            if isinstance(item, BlobPrefix):
                prefixes.add(name)

                blobs.append(self._serialize_blob_prefix(request, item, name))
            else:
                candidate_blobs.append(self._serialize_blob(request, item, name))

        # Paths are returned as both blobs and as prefixes
        for blob in candidate_blobs:
            if blob["size"] or blob["name"] not in prefixes:
                blobs.append(blob)

        return Response(blobs)

    def _serialize_blob_prefix(self, request, item, name):
        return {
            "name": name,
            "type": "folder",
            "url": reverse(
                f"{self.namespace}:files",
                kwargs={"blob": item["name"]},
                request=request,
            ),
        }

    def _serialize_blob(self, request, item, name):
        return {
            "name": name,
            "type": "file",
            "size": item["size"],
            "url": reverse(
                f"{self.namespace}:download",
                kwargs={"blob": item["name"]},
                request=request,
            ),
        }

    def _list_root_folders(self, request):
        # Visible folders must be limited to samples accessible to the user
        samples = frozenset(
            sample.name for sample in self.list_view.query_samples(request)
        )

        blobs = []
        client = self.get_container_client()
        for item in client.walk_blobs():
            if isinstance(item, BlobPrefix):
                name = PurePosixPath(item["name"]).name
                if name in samples:
                    blobs.append(self._serialize_blob_prefix(request, item, name))

        return Response(blobs)


class DownloadFileBase(APIView):
    list_model = None
    get_sas_url = None

    def get(self, request, blob="", format=None):
        if not request.user.is_authenticated:
            raise AssertionError("user is not authenticated")

        blob, blob_parts = _split_blob_path(blob)

        # verify that the current user can access the sample
        self.list_model.check_user_access(user=request.user, name=blob_parts[0])

        return HttpResponseRedirect(redirect_to=self.get_sas_url(blob.as_posix()))


def error400(*args, **kwargs):
    return _response_from_exception(ParseError)


def error403(*args, **kwargs):
    return _response_from_exception(PermissionDenied)


def error404(*args, **kwargs):
    return _response_from_exception(NotFound)


def error500(*args, **kwargs):
    return _response_from_exception(APIException)


def _response_from_exception(exception):
    return HttpResponse(
        json.dumps(
            {
                "detail": str(exception.default_detail),
                "status_code": exception.status_code,
            }
        ),
        content_type="application/json",
        status=exception.status_code,
    )


def _split_blob_path(blob):
    blob = PurePosixPath(blob)
    blob_parts = blob.parts
    if not blob_parts or ".." in blob_parts:
        # disallow tomfoolery
        raise ValidationError("invalid path")

    return blob, blob_parts

from django.urls import re_path

from .views import ListRequestsView, ListFilesView, DownloadFileView

app_name = "ngs"

urlpatterns = [
    re_path(r"^requests/?$", ListRequestsView.as_view(), name="requests"),
    re_path(r"^files/(?P<blob>.*)", ListFilesView.as_view(), name="files"),
    re_path(r"^download/(?P<blob>.*)", DownloadFileView.as_view(), name="download"),
]

from django.urls import re_path

from .views import DownloadFileView, ListSamplesView, ListFilesView

app_name = "ngs"

urlpatterns = [
    re_path(r"^samples/?$", ListSamplesView.as_view(), name="samples"),
    re_path(r"^files/(?P<blob>.*)", ListFilesView.as_view(), name="files"),
    re_path(r"^download/(?P<blob>.*)", DownloadFileView.as_view(), name="download"),
]

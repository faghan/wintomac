"""data_broker URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include

from data_broker.common import views as common_views


urlpatterns = [
    path("ngs/", include("data_broker.ngs.urls", "ngs")),
    path("proteomics/", include("data_broker.proteomics.urls", "proteomics")),
]

handler400 = common_views.error400
handler403 = common_views.error403
handler404 = common_views.error404
handler500 = common_views.error500

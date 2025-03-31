import json

from rest_framework import serializers
from rest_framework.reverse import reverse

from .models import (
    LimsRawSequencingSubmissionSample,
    LimsRawAcProteomics,
    LimsRawProteomicsSubmissionSample,
    LimsRawAnalyticalSubmissionSample,
)


class LimsRawSequencingSubmissionSampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimsRawSequencingSubmissionSample
        exclude = ["dw_creator"]

    # custom_fields = serializers.SerializerMethodField()
    creator = serializers.ReadOnlyField(source="dw_creator.handle")
    files_url = serializers.SerializerMethodField()

    # def get_custom_fields(self, obj):
    #     return json.loads(obj.custom_fields)

    def get_files_url(self, obj):
        return reverse(
            "ngs:files", kwargs={"blob": obj.name}, request=self.context["request"]
        )


class LimsRawProteomicsSubmissionSampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimsRawProteomicsSubmissionSample
        exclude = ["dw_creator"]

    creator = serializers.ReadOnlyField(source="dw_creator.handle")


class LimsRawAnalyticalSubmissionSampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimsRawAnalyticalSubmissionSample
        exclude = ["dw_creator"]

    creator = serializers.ReadOnlyField(source="dw_creator.handle")


class LimsRawAcProteomicsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimsRawAcProteomics
        exclude = ["dw_creator", "dw_requestor"]

    creator = serializers.ReadOnlyField(source="dw_creator.handle")
    files_url = serializers.SerializerMethodField()
    requestor = serializers.ReadOnlyField(source="dw_requestor.handle")
    analytical_submission_samples = LimsRawAnalyticalSubmissionSampleSerializer(
        many=True
    )
    proteomics_submission_samples = LimsRawProteomicsSubmissionSampleSerializer(
        many=True
    )

    def get_files_url(self, obj):
        return reverse(
            "proteomics:files",
            kwargs={"blob": obj.name},
            request=self.context["request"],
        )

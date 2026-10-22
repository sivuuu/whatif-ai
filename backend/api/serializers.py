"""Django REST serializers"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Project, ScenarioSpec, SimulationConfig,
    SimulationRun, RunMetric, SimulationResult, GeneratedReport
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class ProjectSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    scenario_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ["id", "name", "description", "owner", "created_at", "updated_at", "scenario_count"]

    def get_scenario_count(self, obj):
        return obj.scenarios.count()


class ScenarioSpecSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScenarioSpec
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class SimulationConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimulationConfig
        fields = "__all__"
        read_only_fields = ["created_at"]


class RunMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = RunMetric
        fields = "__all__"


class SimulationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimulationResult
        fields = "__all__"


class SimulationRunSerializer(serializers.ModelSerializer):
    metrics = RunMetricSerializer(many=True, read_only=True)
    result = SimulationResultSerializer(read_only=True)

    class Meta:
        model = SimulationRun
        fields = "__all__"
        read_only_fields = ["created_at", "started_at", "completed_at", "status"]


class GeneratedReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedReport
        fields = "__all__"
        read_only_fields = ["created_at"]

"""
WhatIf AI – Django REST views
"""
import json
import threading
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import (
    GeneratedReport, Project, RunMetric, ScenarioSpec,
    SimulationConfig, SimulationResult, SimulationRun,
)
from .serializers import (
    GeneratedReportSerializer, ProjectSerializer, RunMetricSerializer,
    ScenarioSpecSerializer, SimulationConfigSerializer,
    SimulationResultSerializer, SimulationRunSerializer,
)
from simulation.engine import dispatch_simulation, SimulationError
from agents.workflow import run_workflow


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    username = request.data.get("username")
    password = request.data.get("password")
    email = request.data.get("email", "")
    if not username or not password:
        return Response({"error": "username and password required"}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({"error": "username already exists"}, status=400)
    user = User.objects.create_user(username=username, password=password, email=email)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user_id": user.pk, "username": user.username})


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(username=username, password=password)
    if user is None:
        return Response({"error": "Invalid credentials"}, status=400)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user_id": user.pk, "username": user.username})


@api_view(["POST"])
def logout_view(request):
    request.user.auth_token.delete()
    return Response({"detail": "Logged out."})


# ---------------------------------------------------------------------------
# Project ViewSet
# ---------------------------------------------------------------------------

class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Project.objects.filter(owner=self.request.user)
        return Project.objects.none()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


# ---------------------------------------------------------------------------
# Scenario ViewSet
# ---------------------------------------------------------------------------

class ScenarioViewSet(viewsets.ModelViewSet):
    serializer_class = ScenarioSpecSerializer

    def get_queryset(self):
        qs = ScenarioSpec.objects.all()
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    @action(detail=False, methods=["post"])
    def interpret(self, request):
        """
        POST /api/scenarios/interpret/
        Run the NL→structured workflow and return the extracted variables.
        Does NOT save to the database.
        """
        raw_input = request.data.get("raw_input", "")
        seed = int(request.data.get("seed", 42))
        if not raw_input:
            return Response({"error": "raw_input is required"}, status=400)

        state = run_workflow(raw_input, seed=seed)
        return Response({
            "domain": state.domain,
            "variables": state.variables,
            "constraints": state.constraints,
            "assumptions": state.assumptions,
            "clarification_questions": state.clarification_questions,
            "needs_clarification": state.needs_clarification,
            "errors": state.errors,
            "step_log": state.step_log,
        })

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        """
        POST /api/scenarios/<id>/validate/
        Re-run assumption validation on the current variables.
        """
        scenario = self.get_object()
        from agents.workflow import assumption_validator, WorkflowState
        state = WorkflowState(
            raw_input=scenario.raw_input,
            variables=scenario.variables,
            constraints=scenario.constraints,
        )
        state = assumption_validator(state)
        if state.errors:
            scenario.status = "needs_clarification"
        else:
            scenario.status = "validated"
        scenario.save()
        return Response({
            "status": scenario.status,
            "errors": state.errors,
        })


# ---------------------------------------------------------------------------
# Simulation Config + Run ViewSets
# ---------------------------------------------------------------------------

class SimulationConfigViewSet(viewsets.ModelViewSet):
    serializer_class = SimulationConfigSerializer
    queryset = SimulationConfig.objects.all()

    def get_queryset(self):
        qs = SimulationConfig.objects.all()
        scenario_id = self.request.query_params.get("scenario")
        if scenario_id:
            qs = qs.filter(scenario_id=scenario_id)
        return qs


class SimulationRunViewSet(viewsets.ModelViewSet):
    serializer_class = SimulationRunSerializer
    queryset = SimulationRun.objects.all()

    @action(detail=False, methods=["post"])
    def launch(self, request):
        """
        POST /api/runs/launch/
        {
          "scenario_id": 1,
          "method": "sensitivity" | "monte_carlo" | "scenario_comparison",
          "parameters": {...},
          "seed": 42
        }
        Executes synchronously (thread-safe for SQLite dev).
        """
        scenario_id = request.data.get("scenario_id")
        method = request.data.get("method", "scenario_comparison")
        parameters = request.data.get("parameters", {})
        seed = int(request.data.get("seed", 42))

        try:
            scenario = ScenarioSpec.objects.get(pk=scenario_id)
        except ScenarioSpec.DoesNotExist:
            return Response({"error": "Scenario not found"}, status=404)

        # Create config + run records
        config, _ = SimulationConfig.objects.get_or_create(
            scenario=scenario,
            method=method,
            defaults={"parameters": parameters, "seed": seed},
        )
        run = SimulationRun.objects.create(
            config=config,
            status="running",
            seed=seed,
            algorithm_version="1.0.0",
            started_at=datetime.now(timezone.utc),
        )

        try:
            result = dispatch_simulation(
                method=method,
                domain=scenario.domain,
                variables=scenario.variables,
                constraints=scenario.constraints,
                parameters=parameters,
                seed=seed,
            )
            # Store metrics
            _store_metrics(run, result)
            SimulationResult.objects.create(
                run=run,
                summary=_extract_summary(result),
                series_data=_extract_series(result),
                sensitivity_data=result.get("sensitivities", []),
                scenario_comparison=result.get("scenarios", {}),
                constraint_violations=result.get("constraint_violations", []),
                methodology_notes=f"Method: {method}, Seed: {seed}, Engine: {result.get('engine_version', '?')}",
            )
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.save()
            return Response(SimulationRunSerializer(run).data, status=201)

        except (SimulationError, Exception) as e:
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)
            run.save()
            return Response({"error": str(e), "run_id": run.pk}, status=400)

    @action(detail=True, methods=["get"])
    def compare(self, request, pk=None):
        """
        GET /api/runs/<id>/compare/?other=<id2>
        Compare two simulation runs.
        """
        run1 = self.get_object()
        other_id = request.query_params.get("other")
        try:
            run2 = SimulationRun.objects.get(pk=other_id)
        except (SimulationRun.DoesNotExist, TypeError):
            return Response({"error": "other run not found"}, status=404)

        def _result_data(r):
            try:
                res = r.result
                return {
                    "run_id": r.pk,
                    "status": r.status,
                    "method": r.config.method,
                    "summary": res.summary,
                    "constraint_violations": res.constraint_violations,
                }
            except Exception:
                return {"run_id": r.pk, "status": r.status, "error": "no result"}

        return Response({
            "run_a": _result_data(run1),
            "run_b": _result_data(run2),
        })

    @action(detail=True, methods=["post"])
    def export_report(self, request, pk=None):
        """POST /api/runs/<id>/export_report/"""
        run = self.get_object()
        try:
            res = run.result
        except Exception:
            return Response({"error": "Run has no result"}, status=400)

        content = {
            "run_id": run.pk,
            "scenario": ScenarioSpecSerializer(run.config.scenario).data,
            "config": SimulationConfigSerializer(run.config).data,
            "summary": res.summary,
            "series_data": res.series_data,
            "sensitivity_data": res.sensitivity_data,
            "constraint_violations": res.constraint_violations,
            "methodology_notes": res.methodology_notes,
            "explanation": res.explanation,
        }
        report = GeneratedReport.objects.create(
            run=run,
            title=f"Report: {run.config.scenario.title} ({run.config.method})",
            content_json=content,
            created_by=request.user if request.user.is_authenticated else None,
        )
        return Response(GeneratedReportSerializer(report).data, status=201)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store_metrics(run: SimulationRun, result: dict):
    method = result.get("method", "")
    if method == "sensitivity":
        baseline = result.get("baseline", {})
        for k, v in baseline.items():
            if isinstance(v, (int, float)):
                RunMetric.objects.create(run=run, name=k, value=float(v))
    elif method == "monte_carlo":
        for metric, s in result.get("statistics", {}).items():
            if isinstance(s, dict) and "p50" in s:
                RunMetric.objects.create(
                    run=run, name=metric, value=s.get("p50"),
                    percentile_5=s.get("p5"),
                    percentile_25=s.get("p25"),
                    percentile_50=s.get("p50"),
                    percentile_75=s.get("p75"),
                    percentile_95=s.get("p95"),
                )
    elif method == "scenario_comparison":
        for scenario_name, data in result.get("scenarios", {}).items():
            for k, v in data.items():
                if isinstance(v, (int, float)):
                    RunMetric.objects.create(
                        run=run, name=f"{scenario_name}.{k}", value=float(v)
                    )


def _extract_summary(result: dict) -> dict:
    method = result.get("method", "")
    if method == "sensitivity":
        return result.get("baseline", {})
    elif method == "monte_carlo":
        return {k: v for k, v in result.get("statistics", {}).items()}
    elif method == "scenario_comparison":
        return {
            name: {"total_monthly_cost": data.get("total_monthly_cost")}
            for name, data in result.get("scenarios", {}).items()
            if "error" not in data
        }
    return {}


def _extract_series(result: dict) -> dict:
    method = result.get("method", "")
    if method == "sensitivity":
        return {"tornado": result.get("tornado", []), "sensitivities": result.get("sensitivities", [])}
    elif method == "monte_carlo":
        return {"histogram": result.get("histogram", {})}
    elif method == "scenario_comparison":
        return {"series": result.get("series", {})}
    return {}


# ---------------------------------------------------------------------------
# Quick-run endpoint (full workflow from NL)
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([AllowAny])
def quick_run(request):
    """
    POST /api/quick-run/
    { "raw_input": "...", "seed": 42 }
    Run the full multi-agent workflow and return the complete report.
    Does NOT persist to the database — for demo/exploration use.
    """
    raw_input = request.data.get("raw_input", "")
    seed = int(request.data.get("seed", 42))
    if not raw_input:
        return Response({"error": "raw_input is required"}, status=400)

    state = run_workflow(raw_input, seed=seed)
    return Response(state.report)


@api_view(["GET"])
@permission_classes([AllowAny])
def dashboard_stats(request):
    """GET /api/stats/ – overview numbers for the dashboard."""
    return Response({
        "total_scenarios": ScenarioSpec.objects.count(),
        "total_runs": SimulationRun.objects.count(),
        "completed_runs": SimulationRun.objects.filter(status="completed").count(),
        "failed_runs": SimulationRun.objects.filter(status="failed").count(),
        "recent_scenarios": ScenarioSpecSerializer(
            ScenarioSpec.objects.order_by("-created_at")[:5], many=True
        ).data,
        "recent_runs": SimulationRunSerializer(
            SimulationRun.objects.order_by("-created_at")[:5], many=True
        ).data,
    })

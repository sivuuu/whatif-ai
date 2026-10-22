"""Django models for WhatIf AI"""
from django.db import models
from django.contrib.auth.models import User
import json


class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class ScenarioSpec(models.Model):
    """A structured scenario specification extracted from natural language."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="scenarios")
    title = models.CharField(max_length=300)
    description = models.TextField()
    raw_input = models.TextField()  # original NL text
    domain = models.CharField(max_length=100, default="cloud_infrastructure")
    variables = models.JSONField(default=dict)       # {name: {value, unit, distribution, min, max}}
    constraints = models.JSONField(default=list)     # [{name, operator, threshold, unit}]
    assumptions = models.JSONField(default=list)     # [{text, source, confidence}]
    status = models.CharField(
        max_length=30,
        choices=[
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("needs_clarification", "Needs Clarification"),
        ],
        default="draft",
    )
    clarification_questions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class SimulationConfig(models.Model):
    """Configuration for a specific simulation run."""
    METHODS = [
        ("sensitivity", "Sensitivity Analysis"),
        ("monte_carlo", "Monte Carlo"),
        ("scenario_comparison", "Scenario Comparison"),
    ]
    scenario = models.ForeignKey(ScenarioSpec, on_delete=models.CASCADE, related_name="sim_configs")
    method = models.CharField(max_length=30, choices=METHODS)
    parameters = models.JSONField(default=dict)  # method-specific params
    seed = models.IntegerField(default=42)
    n_trials = models.IntegerField(default=10000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.scenario.title} – {self.method}"


class SimulationRun(models.Model):
    """A single execution of a simulation configuration."""
    STATUS = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    config = models.ForeignKey(SimulationConfig, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    algorithm_version = models.CharField(max_length=50, default="1.0.0")
    seed = models.IntegerField()
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Run #{self.pk} ({self.status})"


class RunMetric(models.Model):
    """Individual metrics produced by a simulation run."""
    run = models.ForeignKey(SimulationRun, on_delete=models.CASCADE, related_name="metrics")
    name = models.CharField(max_length=200)
    value = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    percentile_5 = models.FloatField(null=True, blank=True)
    percentile_25 = models.FloatField(null=True, blank=True)
    percentile_50 = models.FloatField(null=True, blank=True)
    percentile_75 = models.FloatField(null=True, blank=True)
    percentile_95 = models.FloatField(null=True, blank=True)
    metadata = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.run} – {self.name}"


class SimulationResult(models.Model):
    """Full result payload of a completed simulation run."""
    run = models.OneToOneField(SimulationRun, on_delete=models.CASCADE, related_name="result")
    summary = models.JSONField(default=dict)       # high-level KPIs
    series_data = models.JSONField(default=dict)   # chart-ready arrays
    sensitivity_data = models.JSONField(default=dict)
    scenario_comparison = models.JSONField(default=dict)
    constraint_violations = models.JSONField(default=list)
    explanation = models.TextField(blank=True)
    methodology_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class GeneratedReport(models.Model):
    """Exported decision report for a run."""
    run = models.ForeignKey(SimulationRun, on_delete=models.CASCADE, related_name="reports")
    title = models.CharField(max_length=300)
    content_json = models.JSONField(default=dict)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

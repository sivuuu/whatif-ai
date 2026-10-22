"""Django admin registration"""
from django.contrib import admin
from .models import (
    Project, ScenarioSpec, SimulationConfig,
    SimulationRun, RunMetric, SimulationResult, GeneratedReport
)

admin.site.register(Project)
admin.site.register(ScenarioSpec)
admin.site.register(SimulationConfig)
admin.site.register(SimulationRun)
admin.site.register(RunMetric)
admin.site.register(SimulationResult)
admin.site.register(GeneratedReport)

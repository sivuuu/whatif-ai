"""API URL routing"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"projects", views.ProjectViewSet, basename="project")
router.register(r"scenarios", views.ScenarioViewSet, basename="scenario")
router.register(r"configs", views.SimulationConfigViewSet, basename="config")
router.register(r"runs", views.SimulationRunViewSet, basename="run")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/register/", views.register),
    path("auth/login/", views.login_view),
    path("auth/logout/", views.logout_view),
    path("quick-run/", views.quick_run),
    path("stats/", views.dashboard_stats),
]

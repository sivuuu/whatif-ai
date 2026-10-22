"""
Django management command to seed sample data.
Usage: python manage.py seed_data
"""
import json
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import Project, ScenarioSpec


class Command(BaseCommand):
    help = "Seed sample scenario data for demonstration"

    def handle(self, *args, **options):
        # Create demo user
        user, created = User.objects.get_or_create(username="demo")
        if created:
            user.set_password("whatif2024")
            user.save()
            self.stdout.write(self.style.SUCCESS("Created demo user (password: whatif2024)"))

        # Create demo project
        project, _ = Project.objects.get_or_create(
            name="Cloud Infrastructure Planning",
            defaults={"owner": user, "description": "Demonstration project for cloud cost scenario planning."},
        )

        # Load sample scenarios
        sample_file = os.path.join(
            os.path.dirname(__file__), "../../../../sample_scenarios/cloud_infrastructure.json"
        )
        if not os.path.exists(sample_file):
            self.stdout.write(self.style.WARNING("Sample scenarios file not found"))
            return

        with open(sample_file) as f:
            data = json.load(f)

        for s in data["scenarios"]:
            obj, created = ScenarioSpec.objects.get_or_create(
                title=s["title"],
                project=project,
                defaults={
                    "raw_input": s["raw_input"],
                    "domain": s["domain"],
                    "variables": s["variables"],
                    "constraints": s["constraints"],
                    "assumptions": s["assumptions"],
                    "status": "validated",
                },
            )
            action = "Created" if created else "Already exists"
            self.stdout.write(f"{action}: {obj.title}")

        self.stdout.write(self.style.SUCCESS("Seed data complete."))

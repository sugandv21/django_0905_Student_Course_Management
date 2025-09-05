from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import FileExtensionValidator

User = settings.AUTH_USER_MODEL

class Course(models.Model):
    DEPARTMENTS = [
        ('CS', 'Computer Science'),
        ('AI', 'Artificial Intelligence'),
        ('FIN', 'Finance'),
        ('MKT', 'Marketing'),
        ('MGMT', 'Management'),
        ('IT', 'Information Technology'),
    ]

    title = models.CharField(max_length=200)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'is_staff': True},
        related_name='courses_taught'
    )
    description = models.TextField(blank=True)
    department = models.CharField(max_length=50, choices=DEPARTMENTS, blank=True)

    def __str__(self):
        return self.title



class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='studentprofile')
    roll_number = models.CharField(max_length=50, unique=True)

    def __str__(self):
        name = self.user.get_full_name() or self.user.username
        return f"{name} ({self.roll_number})"


class Enrollment(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_on = models.DateTimeField(default=timezone.now)
    active = models.BooleanField(default=True)
    # optional summary grade for the enrollment
    grade = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        unique_together = ('student', 'course')
        ordering = ['-enrolled_on']

    def __str__(self):
        return f"{self.student} → {self.course}"


class AssignmentSubmission(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='submissions')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='submissions')
    file = models.FileField(
        upload_to='assignments/%Y/%m/%d/',
        validators=[FileExtensionValidator(['pdf'])],
        help_text='Upload PDF file only'
    )
    submitted_at = models.DateTimeField(default=timezone.now)

    # grading fields
    graded = models.BooleanField(default=False)
    grade = models.CharField(max_length=10, blank=True, null=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_submissions')
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Submission {self.pk} by {self.student} for {self.course}"

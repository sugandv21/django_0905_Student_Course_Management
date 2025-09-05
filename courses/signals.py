# courses/signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.contrib.auth import get_user_model
from .models import StudentProfile, AssignmentSubmission

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def create_student_profile_on_user_create(sender, instance, created, **kwargs):
    """
    Create a StudentProfile automatically for regular (non-staff) users if not present.
    If the user was created as instructor (is_staff=True) we do not create a StudentProfile.
    Also sends a welcome email to the user's email (if provided).
    """
    if created and not instance.is_staff:
        # create with placeholder roll if not already existing (unique roll required)
        default_roll = f"ROLL{instance.pk:05d}"
        StudentProfile.objects.get_or_create(user=instance, defaults={'roll_number': default_roll})

        # prepare email details
        recipient = instance.email
        if not recipient:
            logger.info("New user created but no email provided; skipping welcome email for user %s", instance)
            return

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None) or 'no-reply@localhost'

        subject = 'Welcome to StudentCourses'
        plain_message = (
            f'Hi {instance.get_full_name() or instance.username},\n\n'
            'Welcome to StudentCourses!\n\n'
            'Your student account has been created. You can now log in and enroll in courses.\n\n'
            'Regards,\nStudentCourses Team'
        )

        # Optional HTML message (makes email look nicer in inbox)
        html_message = f"""
        <p>Hi <strong>{instance.get_full_name() or instance.username}</strong>,</p>
        <p>Welcome to <strong>StudentCourses</strong>!</p>
        <p>Your student account has been created. You can now log in and enroll in courses.</p>
        <p>Regards,<br/>StudentCourses Team</p>
        """

        try:
            # Use EmailMultiAlternatives so we can provide both plain and html
            msg = EmailMultiAlternatives(subject, plain_message, from_email, [recipient])
            msg.attach_alternative(html_message, "text/html")
            # Note: keep fail_silently=True in production-like settings to avoid breaking signup flow
            msg.send(fail_silently=True)
            logger.info("Sent welcome email to %s", recipient)
        except Exception as exc:
            # Log exception; do not re-raise so registration flow stays intact
            logger.exception("Failed to send welcome email to %s: %s", recipient, exc)


@receiver(post_save, sender=AssignmentSubmission)
def notify_student_on_graded(sender, instance, created, **kwargs):
    """
    When an existing submission is saved and it's now graded, send an email to the student.
    """
    # Only react on grading (not on initial creation)
    if not created and instance.graded:
        recipient = getattr(instance.student.user, 'email', None)
        if not recipient:
            logger.info("Submission graded but student has no email: submission id %s", instance.pk)
            return

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None) or 'no-reply@localhost'

        subject = f'Your assignment for {instance.course.title} has been graded'
        plain_message = (
            f'Hello {instance.student.user.get_full_name() or instance.student.user.username},\n\n'
            f'Your submission for the course \"{instance.course.title}\" was graded.\n\n'
            f'Grade: {instance.grade}\n\n'
            f'Feedback:\n{instance.feedback or "No feedback provided."}\n\n'
            'Regards,\nStudentCourses'
        )

        html_message = f"""
        <p>Hello <strong>{instance.student.user.get_full_name() or instance.student.user.username}</strong>,</p>
        <p>Your submission for the course <strong>{instance.course.title}</strong> was graded.</p>
        <p><strong>Grade:</strong> {instance.grade}</p>
        <p><strong>Feedback:</strong><br/>{(instance.feedback or 'No feedback provided.')}</p>
        <p>Regards,<br/>StudentCourses</p>
        """

        try:
            msg = EmailMultiAlternatives(subject, plain_message, from_email, [recipient])
            msg.attach_alternative(html_message, "text/html")
            msg.send(fail_silently=True)
            logger.info("Sent graded-notification to %s for submission %s", recipient, instance.pk)
        except Exception as exc:
            logger.exception("Failed to send graded-notification to %s for submission %s: %s", recipient, instance.pk, exc)

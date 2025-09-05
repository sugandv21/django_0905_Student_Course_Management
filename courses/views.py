# courses/views.py
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.views import LoginView

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .models import Course, StudentProfile, Enrollment, AssignmentSubmission
from .forms import (
    EnrollmentForm,
    AssignmentSubmissionForm,
    RegistrationForm,
    CourseForm,
)

logger = logging.getLogger(__name__)


# ---------------- Assignment upload ----------------
class AssignmentCreateView(LoginRequiredMixin, CreateView):
    """
    Students upload assignments (PDF). Form limits course choices to student's active enrollments (or instructor's courses).
    """
    model = AssignmentSubmission
    form_class = AssignmentSubmissionForm
    template_name = 'courses/upload_assignment.html'
    success_url = reverse_lazy('courses:my_enrollments')

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw.update({'user': self.request.user})
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx.get('form') or self.get_form()
        qs = form.fields['course'].queryset
        ctx['no_courses'] = (qs is None) or (hasattr(qs, 'count') and qs.count() == 0)
        return ctx

    def form_valid(self, form):
        # ensure studentprofile exists
        try:
            profile = self.request.user.studentprofile
        except StudentProfile.DoesNotExist:
            messages.error(self.request, "Student profile missing. Contact admin.")
            return redirect('courses:list')

        # ensure selected course is among student's active enrollments (unless user is staff/superuser)
        selected_course = form.cleaned_data.get('course')
        if selected_course is None:
            messages.error(self.request, "Please choose a course.")
            return redirect('courses:upload_assignment')

        if not (self.request.user.is_staff or self.request.user.is_superuser):
            enrolled_course_ids = list(profile.enrollments.filter(active=True).values_list('course_id', flat=True))
            if selected_course.id not in enrolled_course_ids:
                messages.error(self.request, "Selected course is not in your active enrollments.")
                return redirect('courses:list')

        # Save submission
        submission = form.save(commit=False)
        submission.student = profile
        submission.submitted_at = timezone.now()
        submission.save()

        # IMPORTANT: set self.object so get_success_url() / other generic machinery won't crash
        self.object = submission

        messages.success(self.request, "Assignment uploaded successfully.")
        logger.info("Assignment uploaded id=%s by user=%s for course=%s", submission.pk, self.request.user, submission.course_id)
        # return redirect to success_url
        return redirect(self.get_success_url())


# ---------------- Course creation (instructors only) ----------------
class CourseCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/course_form.html'
    success_url = reverse_lazy('courses:list')

    def test_func(self):
        # require staff (or superuser) to create via this view
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "Only instructor accounts can create courses. Contact admin to make you an instructor.")
        return super().handle_no_permission()

    def form_valid(self, form):
        try:
            obj = form.save(commit=False)
            obj.instructor = self.request.user
            obj.save()
            messages.success(self.request, "Course created successfully.")
            logger.info("Course created id=%s title=%s by instructor=%s", obj.pk, obj.title, self.request.user)
            return redirect(reverse('courses:detail', args=[obj.pk]))
        except Exception as exc:
            logger.exception("Failed to save course: %s", exc)
            form.add_error(None, "An error occurred while saving the course.")
            return super().form_invalid(form)


# ---------------- Course list / detail ----------------
class CourseListView(ListView):
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'
    paginate_by = 4

    def get_queryset(self):
        qs = super().get_queryset().select_related('instructor')
        dept = self.request.GET.get('department')
        if dept:
            qs = qs.filter(department__iexact=dept)
        return qs


class CourseDetailView(DetailView):
    model = Course
    template_name = 'courses/course_detail.html'
    context_object_name = 'course'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        is_enrolled = False
        if user.is_authenticated:
            try:
                profile = user.studentprofile
            except StudentProfile.DoesNotExist:
                profile = None
            if profile:
                is_enrolled = Enrollment.objects.filter(student=profile, course=self.object, active=True).exists()
        ctx['is_enrolled'] = is_enrolled
        return ctx


# ---------------- Enroll toggle (POST-only) ----------------
@login_required
@require_POST
def enroll_toggle(request, pk):
    if request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "Instructor/staff accounts cannot enroll as students.")
        return redirect('courses:detail', pk=pk)

    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        messages.error(request, "Student profile not found. Contact admin.")
        return redirect('courses:detail', pk=pk)

    course = get_object_or_404(Course, pk=pk)

    enrollment, created = Enrollment.objects.get_or_create(student=profile, course=course, defaults={'active': True})

    if created:
        messages.success(request, f"You have been enrolled in '{course.title}'.")
        logger.info("User %s enrolled in course %s", request.user, course.pk)
    else:
        # toggle active
        enrollment.active = not enrollment.active
        enrollment.save(update_fields=['active'])
        if enrollment.active:
            enrollment.enrolled_on = timezone.now()
            enrollment.save(update_fields=['enrolled_on'])
            messages.success(request, f"You have been re-enrolled in '{course.title}'.")
            logger.info("User %s re-enrolled in course %s", request.user, course.pk)
        else:
            messages.success(request, f"You have dropped '{course.title}'.")
            logger.info("User %s dropped course %s", request.user, course.pk)

    return redirect('courses:detail', pk=pk)


# ---------------- Submissions list & detail ----------------
class SubmissionListView(LoginRequiredMixin, ListView):
    model = AssignmentSubmission
    template_name = 'courses/submissions_list.html'
    context_object_name = 'submissions'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        qs = AssignmentSubmission.objects.select_related('student__user', 'course', 'graded_by').order_by('-submitted_at')

        course_id = self.request.GET.get('course')

        # Staff or superuser: see everything (optionally filter by course)
        if user.is_superuser or user.is_staff:
            return qs.filter(course_id=course_id) if course_id else qs

        # Instructor: courses where Course.instructor == user (non-staff instructor)
        instr_qs = Course.objects.filter(instructor=user)
        if instr_qs.exists():
            if course_id:
                return qs.filter(course_id=course_id, course__in=instr_qs)
            return qs.filter(course__in=instr_qs)

        # Student: only their own submissions
        try:
            profile = user.studentprofile
        except StudentProfile.DoesNotExist:
            return AssignmentSubmission.objects.none()

        if course_id:
            return qs.filter(student=profile, course_id=course_id)
        return qs.filter(student=profile)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # Debug info for staff/instructors/superuser
        if user.is_superuser or user.is_staff or Course.objects.filter(instructor=user).exists():
            instr_qs = Course.objects.filter(instructor=user) if not (user.is_superuser or user.is_staff) else Course.objects.all()
            instructor_courses = []
            for c in instr_qs:
                instructor_courses.append({
                    'id': c.id,
                    'title': c.title,
                    'submissions_count': AssignmentSubmission.objects.filter(course=c).count()
                })
            ctx['debug_instructor_courses'] = instructor_courses
            ctx['debug_course_param'] = self.request.GET.get('course')
            ctx['debug_total_submissions'] = AssignmentSubmission.objects.count()
        return ctx


class SubmissionDetailView(LoginRequiredMixin, DetailView):
    model = AssignmentSubmission
    template_name = 'courses/submission_detail.html'
    context_object_name = 'submission'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        user = request.user

        # Student owner?
        is_owner = hasattr(user, 'studentprofile') and (self.object.student == getattr(user, 'studentprofile', None))
        # Course instructor?
        is_course_instructor = (self.object.course.instructor_id == user.id)
        # Staff or superuser may view
        if user.is_superuser or user.is_staff or is_owner or is_course_instructor:
            return super().dispatch(request, *args, **kwargs)

        messages.error(request, "You do not have permission to view this submission.")
        return redirect('courses:list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        # instructor, staff or superuser may grade
        ctx['can_grade'] = user.is_superuser or user.is_staff or (self.object.course.instructor_id == user.id)
        return ctx


# ---------------- Login & Registration ----------------
class CustomLoginView(LoginView):
    template_name = 'registration/login.html'

    def form_valid(self, form):
        role = self.request.POST.get('role')
        user = form.get_user()
        if role == 'student' and user.is_staff and not user.is_superuser:
            form.add_error(None, 'This account is registered as an instructor; choose Instructor role.')
            return super().form_invalid(form)
        if role == 'instructor' and not (user.is_staff or user.is_superuser):
            form.add_error(None, 'This account is not marked as an instructor; choose Student role.')
            return super().form_invalid(form)
        return super().form_valid(form)


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Registration successful for '{user.username}'. Please login.")
            return redirect('login')
        else:
            logger.debug("Registration form invalid: %s", form.errors)
    else:
        form = RegistrationForm()
    return render(request, 'registration/register.html', {'form': form})


# ---------------- Manual enrollment (optional) ----------------
@login_required
def enroll_manual(request):
    if request.method == 'POST':
        form = EnrollmentForm(request.POST)
        if form.is_valid():
            roll = form.cleaned_data['roll_number']
            course = form.cleaned_data['course']
            try:
                profile = StudentProfile.objects.get(roll_number=roll)
            except StudentProfile.DoesNotExist:
                messages.error(request, f"No student found with roll number {roll}.")
                return redirect('courses:enroll_manual')
            Enrollment.objects.get_or_create(student=profile, course=course, defaults={'active': True})
            messages.success(request, f"{profile} enrolled in {course}.")
            return redirect('courses:list')
    else:
        form = EnrollmentForm()
    return render(request, 'courses/enroll_form.html', {'form': form})


# ---------------- My enrollments ----------------
@login_required
def my_enrollments(request):
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        messages.error(request, "You don't have a student profile.")
        return redirect('courses:list')

    enrollments = profile.enrollments.select_related('course')
    return render(request, 'courses/my_enrollments.html', {'enrollments': enrollments})


# ---------------- Grading ----------------
@login_required
def grade_submission(request, pk):
    submission = get_object_or_404(AssignmentSubmission, pk=pk)

    # Only course instructor, staff, or superuser can grade
    if not (request.user.is_superuser or request.user.is_staff or submission.course.instructor_id == request.user.id):
        messages.error(request, "Only the course instructor, staff, or a site administrator can grade this submission.")
        return redirect('courses:submission_detail', pk=submission.pk)

    if request.method == 'POST':
        grade = request.POST.get('grade')
        feedback = request.POST.get('feedback', '')
        submission.grade = grade
        submission.feedback = feedback
        submission.graded = True
        submission.graded_by = request.user
        submission.graded_at = timezone.now()
        submission.save()
        messages.success(request, 'Submission graded and student notified (if email configured).')
        logger.info("Submission %s graded by %s (grade=%s)", submission.pk, request.user, grade)
        return redirect('courses:submission_detail', pk=submission.pk)

    return render(request, 'courses/grade_submission.html', {'submission': submission})

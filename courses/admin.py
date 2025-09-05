from django.contrib import admin
from .models import Course, StudentProfile, Enrollment, AssignmentSubmission


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    readonly_fields = ('enrolled_on',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'department')
    search_fields = ('title', 'instructor__username', 'department')
    list_filter = ('department',)
    inlines = [EnrollmentInline]


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'roll_number', 'email')
    search_fields = ('roll_number', 'user__username', 'user__email')
    list_filter = ('enrollments__course',)

    def email(self, obj):
        return obj.user.email
    email.short_description = 'Email'


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_on', 'active', 'grade')
    search_fields = ('student__roll_number', 'student__user__username', 'course__title')
    list_filter = ('course', 'active')
    raw_id_fields = ('student', )


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'submitted_at', 'graded', 'grade', 'graded_by')
    list_filter = ('graded', 'course')
    search_fields = ('student__roll_number', 'student__user__username', 'course__title')
    readonly_fields = ('submitted_at',)

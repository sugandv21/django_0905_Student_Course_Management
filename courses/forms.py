from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Enrollment, AssignmentSubmission, StudentProfile, Course
from .models import Course

User = get_user_model()

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ('title', 'department', 'description')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Course title'}),
            'department': forms.Select(attrs={'class': 'form-select'}),  # if department has choices, Select; else TextInput
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Short description'}),
        }

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    is_instructor = forms.BooleanField(required=False, initial=False, help_text='Check if registering as an instructor')
    roll_number = forms.CharField(required=False, help_text='If you are a student, provide roll number (optional)')

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'is_instructor', 'roll_number')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if self.cleaned_data.get('is_instructor'):
            # mark as staff (instructor)
            user.is_staff = True
        if commit:
            user.save()
            # if roll_number provided and user is student, create StudentProfile
            if not user.is_staff and self.cleaned_data.get('roll_number'):
                StudentProfile.objects.get_or_create(user=user, defaults={'roll_number': self.cleaned_data['roll_number']})
        return user


class EnrollmentForm(forms.Form):
    roll_number = forms.CharField(max_length=50, label='Student Roll Number')
    course = forms.ModelChoiceField(queryset=Course.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # default to all courses
        self.fields['course'].queryset = Course.objects.all()

           

class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ('course', 'file')
        widgets = {
            'course': forms.Select(attrs={'class':'form-select'}),
            'file': forms.ClearableFileInput(attrs={'class':'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # default: no courses
        self.fields['course'].queryset = Course.objects.none()
        # If user is student, restrict to *their* active enrollments
        if user:
            if user.is_staff:
                # instructors can choose courses they teach (helpful for testing)
                self.fields['course'].queryset = Course.objects.filter(instructor=user)
            else:
                try:
                    profile = user.studentprofile
                except Exception:
                    profile = None
                if profile:
                    course_ids = profile.enrollments.filter(active=True).values_list('course_id', flat=True)
                    if course_ids:
                        self.fields['course'].queryset = Course.objects.filter(id__in=course_ids)


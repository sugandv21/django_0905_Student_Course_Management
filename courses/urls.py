
from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    path('', views.CourseListView.as_view(), name='list'),
    path('create/', views.CourseCreateView.as_view(), name='create'),
    path('course/<int:pk>/', views.CourseDetailView.as_view(), name='detail'),
    path('course/<int:pk>/enroll-toggle/', views.enroll_toggle, name='enroll_toggle'),
    path('submissions/', views.SubmissionListView.as_view(), name='submissions_list'),
    path('submission/<int:pk>/', views.SubmissionDetailView.as_view(), name='submission_detail'),
    path('submission/<int:pk>/grade/', views.grade_submission, name='grade_submission'),
    path('my-enrollments/', views.my_enrollments, name='my_enrollments'),
    path('upload-assignment/', views.AssignmentCreateView.as_view(), name='upload_assignment'),
    path('enroll/', views.enroll_manual, name='enroll_manual'),
]

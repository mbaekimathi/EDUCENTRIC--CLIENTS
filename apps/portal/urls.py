from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("attendance/", views.attendance, name="attendance"),
    path("results/", views.results, name="results"),
    path("timetable/", views.timetable, name="timetable"),
    path("finances/", views.finances, name="finances"),
    path("e-learning/", views.elearning, name="elearning"),
    path("e-learning/<int:subject_id>/", views.elearning_subject, name="elearning_subject"),
    path("api/students/search/", views.student_search, name="student_search"),
    path("switch-student/", views.switch_student, name="switch_student"),
]

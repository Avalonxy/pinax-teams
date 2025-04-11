from django.urls import path

from . import views

app_name = "pinax_teams"

urlpatterns = [
    path("", views.TeamListView.as_view(), name="team_list"),
    path("create/", views.TeamCreateView.as_view(), name="team_create"),
    path("<slug:slug>/", views.TeamDetailView.as_view(), name="team_detail"),
    path("<slug:slug>/update/", views.team_update, name="team_update"),
    path("<slug:slug>/manage/", views.TeamManageView.as_view(), name="team_manage"),
    path("<slug:slug>/join/", views.team_join, name="team_join"),
    path("<slug:slug>/leave/", views.team_leave, name="team_leave"),
    path("<slug:slug>/apply/", views.team_apply, name="team_apply"),
    path("membership/<int:pk>/accept/", views.team_accept, name="team_accept"),
    path("membership/<int:pk>/reject/", views.team_reject, name="team_reject"),
    path("membership/<int:pk>/revoke/", views.team_member_revoke_invite, name="team_member_revoke_invite"),
    path("membership/<int:pk>/resend/", views.team_member_resend_invite, name="team_member_resend_invite"),
    path("membership/<int:pk>/promote/", views.team_member_promote, name="team_member_promote"),
    path("membership/<int:pk>/demote/", views.team_member_demote, name="team_member_demote"),
    path("membership/<int:pk>/remove/", views.team_member_remove, name="team_member_remove"),
    path("autocomplete/", views.autocomplete_users, name="autocomplete_users"),
]

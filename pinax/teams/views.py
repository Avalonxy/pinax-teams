import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import FormView, ListView, TemplateView
from django.views.generic.edit import CreateView
from django.views.generic.detail import DetailView

from account.decorators import login_required
from account.mixins import LoginRequiredMixin
from account.views import SignupView

from .decorators import manager_required, team_required
from .forms import TeamForm, TeamInviteUserForm, TeamSignupForm
from .hooks import hookset
from .models import Membership, Team

MESSAGE_STRINGS = hookset.get_message_strings()


class TeamSignupView(SignupView):

    template_name = "pinax/teams/signup.html"

    def get_form_class(self):
        if self.signup_code:
            return self.form_class
        return TeamSignupForm

    def after_signup(self, form):
        if not self.signup_code:
            self.created_user.teams_created.create(
                name=form.cleaned_data["team"]
            )
        super().after_signup(form)


class TeamCreateView(LoginRequiredMixin, CreateView):

    form_class = TeamForm
    model = Team
    template_name = "pinax/teams/team_form.html"

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.creator = self.request.user
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


class TeamListView(ListView):

    model = Team
    context_object_name = "teams"
    template_name = "pinax/teams/team_list.html"


class TeamDetailView(DetailView):
    model = Team
    template_name = "pinax/teams/team_detail.html"
    context_object_name = "team"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object
        user = self.request.user
        context.update({
            "state": team.state_for(user),
            "role": team.role_for(user),
            "invite_form": TeamInviteUserForm(team=team),
            "can_join": team.can_join(user),
            "can_leave": team.can_leave(user),
            "can_apply": team.can_apply(user),
        })
        return context


@team_required
@login_required
def team_update(request):
    team = request.team
    if not team.is_owner_or_manager(request.user):
        return HttpResponseForbidden()
    if request.method == "POST":
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            return redirect(team.get_absolute_url())
    else:
        form = TeamForm(instance=team)
    return render(request, "pinax/teams/team_form.html", {"form": form, "team": team})


class TeamManageView(TemplateView):

    template_name = "pinax/teams/team_manage.html"

    @method_decorator(manager_required)
    def dispatch(self, *args, **kwargs):
        self.team = self.request.team
        self.role = self.team.role_for(self.request.user)
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            "team": self.team,
            "role": self.role,
            "invite_form": self.get_team_invite_form(),
            "can_join": self.team.can_join(self.request.user),
            "can_leave": self.team.can_leave(self.request.user),
            "can_apply": self.team.can_apply(self.request.user),
        })
        return ctx

    def get_team_invite_form(self):
        return TeamInviteUserForm(team=self.team)


@team_required
@login_required
def team_join(request):
    team = request.team
    state = team.state_for(request.user)

    if team.manager_access == Team.MEMBER_ACCESS_INVITATION and \
       state is None and not request.user.is_staff:
        raise Http404()

    if team.can_join(request.user) and request.method == "POST":
        membership, created = Membership.objects.get_or_create(team=team, user=request.user)
        membership.role = Membership.ROLE_MEMBER
        membership.state = Membership.STATE_AUTO_JOINED
        membership.save()
        messages.success(request, MESSAGE_STRINGS["joined-team"])
    return redirect(team.get_absolute_url())


@team_required
@login_required
def team_leave(request):
    team = request.team
    state = team.state_for(request.user)
    if team.manager_access == Team.MEMBER_ACCESS_INVITATION and \
       state is None and not request.user.is_staff:
        raise Http404()

    if team.can_leave(request.user) and request.method == "POST":
        membership = Membership.objects.get(team=team, user=request.user)
        membership.delete()
        messages.success(request, MESSAGE_STRINGS["left-team"])
        return redirect("pinax_teams:dashboard")
    else:
        return redirect(team.get_absolute_url())


@team_required
@login_required
def team_apply(request):
    team = request.team
    state = team.state_for(request.user)
    if team.manager_access == Team.MEMBER_ACCESS_INVITATION and \
       state is None and not request.user.is_staff:
        raise Http404()

    if team.can_apply(request.user) and request.method == "POST":
        membership, created = Membership.objects.get_or_create(team=team, user=request.user)
        membership.state = Membership.STATE_APPLIED
        membership.save()
        messages.success(request, MESSAGE_STRINGS["applied-to-join"])
    return redirect(team.get_absolute_url())


@login_required
@require_POST
def team_accept(request, pk):
    membership = get_object_or_404(Membership, pk=pk)
    if membership.accept(by=request.user):
        messages.success(request, MESSAGE_STRINGS["accepted-application"])
    return redirect(membership.team.get_absolute_url())


@login_required
@require_POST
def team_reject(request, pk):
    membership = get_object_or_404(Membership, pk=pk)
    if membership.reject(by=request.user):
        messages.success(request, MESSAGE_STRINGS["rejected-application"])
    return redirect(membership.team.get_absolute_url())


class TeamInviteView(FormView):
    http_method_names = ["post"]
    form_class = TeamInviteUserForm

    @method_decorator(manager_required)
    def dispatch(self, *args, **kwargs):
        self.team = self.request.team
        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs.update({"team": self.team})
        return form_kwargs

    def get_unbound_form(self):
        """
        Overrides behavior of FormView.get_form_kwargs
        when method is POST or PUT
        """
        form_kwargs = self.get_form_kwargs()
        # @@@ remove fields that would cause the form to be bound
        # when instantiated
        bound_fields = ["data", "files"]
        for field in bound_fields:
            form_kwargs.pop(field, None)
        return self.get_form_class()(**form_kwargs)

    def after_membership_added(self, form):
        """
        Allows the developer to customize actions that happen after a membership
        was added in form_valid
        """
        pass

    def get_form_success_data(self, form):
        """
        Allows customization of the JSON data returned when a valid form submission occurs.
        """
        data = {
            "html": render_to_string(
                "pinax/teams/_invite_form.html",
                {
                    "invite_form": self.get_unbound_form(),
                    "team": self.team
                },
                request=self.request
            )
        }

        membership = self.membership
        if membership:
            data["membership"] = {
                "id": membership.id,
                "state": membership.state,
                "role": membership.role,
                "user": membership.user.username if membership.user else None,
                "invite": membership.invite.to_email if membership.invite else None
            }
        return data

    def form_valid(self, form):
        self.membership = self.team.invite_user(
            self.request.user,
            form.cleaned_data["email_address"],
            form.cleaned_data["role"]
        )
        self.after_membership_added(form)
        return self.render_to_response(self.get_form_success_data(form))

    def form_invalid(self, form):
        return JsonResponse({
            "html": render_to_string(
                "pinax/teams/_invite_form.html",
                {
                    "invite_form": form,
                    "team": self.team
                },
                request=self.request
            )
        }, status=400)

    def render_to_response(self, context, **response_kwargs):
        return JsonResponse(context)


@manager_required
@require_POST
def team_member_revoke_invite(request, pk):
    membership = get_object_or_404(Membership, pk=pk)
    membership.remove(by=request.user)
    messages.success(request, MESSAGE_STRINGS["revoked-invite"])
    return redirect(membership.team.get_absolute_url())


@manager_required
@require_POST
def team_member_resend_invite(request, pk):
    membership = get_object_or_404(Membership, pk=pk)
    if membership.resend_invite(by=request.user):
        messages.success(request, MESSAGE_STRINGS["resent-invite"])
    return redirect(membership.team.get_absolute_url())


@manager_required
@require_POST
def team_member_promote(request, pk):
    membership = get_object_or_404(Membership, pk=pk)
    if membership.promote(by=request.user):
        messages.success(request, MESSAGE_STRINGS["promoted-member"])
    return redirect(membership.team.get_absolute_url())


@manager_required
@require_POST
def team_member_demote(request, pk):
    membership = get_object_or_404(Membership, pk=pk)
    if membership.demote(by=request.user):
        messages.success(request, MESSAGE_STRINGS["demoted-member"])
    return redirect(membership.team.get_absolute_url())


@manager_required
@require_POST
def team_member_remove(request, pk):
    membership = get_object_or_404(Membership, pk=pk)
    membership.remove(by=request.user)
    messages.success(request, MESSAGE_STRINGS["removed-member"])
    return redirect(membership.team.get_absolute_url())


@team_required
@login_required
def autocomplete_users(request):
    if "q" in request.GET:
        users = get_user_model().objects.filter(
            username__icontains=request.GET["q"]
        ).exclude(
            username=request.user.username
        )
        return JsonResponse({
            "users": [{"username": u.username} for u in users]
        })
    return JsonResponse({"users": []})

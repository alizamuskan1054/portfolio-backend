"""
API ViewSet for Client Management.
"""
from django.db.models import OuterRef, Subquery
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import action
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings


from apps.common.permissions import IsVerifiedAdmin
from apps.common.pagination import StandardResultsPagination
from apps.common.responses import created_response, success_response, error_response
from apps.portfolios.models import Portfolio
from apps.accounts.models import User
from apps.accounts.emails import send_portal_invite_email
from rest_framework.views import APIView
from apps.common.responses import success_response
from .models import Client
from .serializers import ClientSerializer, is_reusable_orphan_user


class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet that provides standard CRUD operations for Clients.
    Also includes Portal Invite actions.
    """
    serializer_class = ClientSerializer
    permission_classes = [IsVerifiedAdmin]
    pagination_class = StandardResultsPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["full_name", "email", "organization"]
    ordering_fields = ["created_at", "full_name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # One subquery gives every row its (non-deleted) portfolio status: no N+1.
        # (Portfolio.objects hides soft-deleted portfolios.)
        return Client.objects.annotate(
            portfolio_status_annot=Subquery(
                Portfolio.objects.filter(client=OuterRef("pk")).values("status")[:1]
            )
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return created_response(data=serializer.data, message="Client created successfully.")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        # Deleted client ka login band: user inactive + purane tokens revoke
        if instance.user_id:
            from apps.accounts.views import revoke_all_tokens
            linked = instance.user
            linked.is_active = False
            linked.save(update_fields=["is_active"])
            revoke_all_tokens(linked)
            instance.portal_status = "disabled"
            instance.save(update_fields=["portal_status", "updated_at"])
        # Client ke saare portfolios ko bhi soft-delete karein
        instance.portfolios.filter(deleted_at__isnull=True).update(deleted_at=timezone.now())
        return success_response(message="Client deleted successfully (can be recovered).")

    # ==========================================
    # PORTAL ACTIONS (NEW)
    # ==========================================

    @action(detail=True, methods=["post"], url_path="invite")
    def invite(self, request, pk=None):
        """
        Generate invite link and send email to client.
        Works for both new invites and resends.
        """
        client = self.get_object()
        
        if client.portal_status == 'active':
            return error_response(message="Client portal is already active.")
        
        # 1. User account resolve karein
        if not client.user:
            existing = User.objects.filter(email__iexact=client.email).first()
            if existing:
                if not is_reusable_orphan_user(existing):
                    return error_response(
                        message="A user with this email already exists in the system. "
                                "Please use a different email for this client."
                    )
                # Purane deleted client ka orphan account: reset karke dobara use karein
                Client.all_objects.filter(user=existing).exclude(pk=client.pk).update(user=None)
                existing.email = client.email
                existing.full_name = client.full_name
                existing.role = "client"
                existing.is_active = False
                existing.email_verified_at = None
                existing.set_unusable_password()
                existing.save()
                user = existing
            else:
                user = User.objects.create_user(
                    email=client.email,
                    full_name=client.full_name,
                    role="client",
                    is_active=False,
                )
            client.user = user
        else:
            user = client.user
            # Agar client ki email edit hui hai, toh user ki email bhi sync karein
            if user.email != client.email:
                if User.objects.filter(email__iexact=client.email).exclude(pk=user.pk).exists():
                    return error_response(message="A user with this new email already exists in the system.")
                user.email = client.email
                user.save()

        client.portal_status = 'invited'
        client.save()

        # 2. Link banayein
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        
        # Frontend URL (settings se read karein)
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
        invite_url = f"{frontend_url}/portal/accept-invite?uid={uid}&token={token}"

        # 3. Email bhejein (Ensure karein ke send_portal_invite_email client.email use kar raha ho)
        try:
            send_portal_invite_email(user, client, invite_url)
            email_sent = True
        except Exception as e:
            email_sent = False 
            print(f"Email sending failed: {e}") 

        return success_response(
            message="Invite sent to client's email." if email_sent else "Invite generated (Email failed).",
            data={"invite_url": invite_url, "email_sent": email_sent, "sent_to": client.email}
        )


class PortalMeView(APIView):
    """Returns the current logged-in client and their portfolios."""
    # Yahan IsAuthenticated use karenge kyunke Client login hai
    from rest_framework.permissions import IsAuthenticated
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not hasattr(user, 'client_profile'):
            return error_response(message="Only clients can access this endpoint.", status_code=403)
            
        client = user.client_profile
        portfolios = Portfolio.objects.filter(client=client)
        
        #  Unread messages count
        from apps.portfolios.models import ContactMessage
        unread_count = ContactMessage.objects.filter(
            portfolio__client=client, is_read=False
        ).count()
        
        data = {
            "client": {
                "id": client.id,
                "full_name": client.full_name,
                "email": client.email,
                "portal_status": client.portal_status,
            },
            "unread_messages_count": unread_count, 
            "portfolio_count": portfolios.count(),
            "portfolio_limit": 5,
            "portfolios": [
                {
                    "id": p.id,
                    "title": p.title,
                    "slug": p.slug,
                    "status": p.status,
                    "template_id": p.template.id
                } for p in portfolios
            ]
        }
        return success_response(data=data)
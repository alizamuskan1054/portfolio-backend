"""
Helpers to send auth-related emails.
Using Django's built-in token generator to avoid needing DB tables for tokens.
"""
from django.conf import settings
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator


def send_verification_email(user):
    """Sends an email with a secure link to verify the account."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    
    # Frontend URL handles the route, then calls our API verify endpoint
    verify_url = f"{settings.FRONTEND_URL}/admin/verify-email?uid={uid}&token={token}"
    
    subject = "Verify your Admin Account"
    message = f"Hi {user.full_name},\n\nPlease verify your account by clicking the link below:\n{verify_url}\n\nThis link expires in 24 hours."
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_password_reset_email(user):
    """Sends an email with a secure link to reset the password."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    
    reset_url = f"{settings.FRONTEND_URL}/admin/reset-password?uid={uid}&token={token}"
    
    subject = "Reset your Password"
    message = f"Hi {user.full_name},\n\nYou requested a password reset. Click the link below to set a new password:\n{reset_url}\n\nThis link expires in 1 hour."
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
def send_portal_invite_email(user, client, invite_url):
    """
    Sends a professional portal invitation email to the client.
    """
    subject = "Invitation: Set up your Client Portal"
    
    message = f"""
    Hi {client.full_name},

    You have been invited by the Admin to access your Client Portal. 
    From your portal, you can manage your portfolios, add academic data, and update your website content.

    Please click the link below to set your password and activate your account:
    
    {invite_url}

    Note: This link will expire in 24 hours.

    If you did not expect this invitation, please ignore this email.

    Best regards,
    The Portfolio Team
    """
    # send_mail Django ki settings (SMTP) use karega
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[client.email],
        fail_silently=False, # Agar SMTP mein masla hua toh error throw karega
    )
"""
Notification banane ke helpers. Yeh kabhi exception bahar nahi phenktay:
notification fail ho jaye to asal action (publish, contact form, ...) chalta rehta hai.

Recipients:
  contact_message                         -> us portfolio ka client
  portfolio_created / portfolio_deleted   -> saare admins (sirf jab client kare)
  portal_activated                        -> saare admins
  portfolio_published / unpublished       -> client kare to admins, admin kare to us ka client
Jo khud action kare, usay uski notification nahi milti.
"""
import logging

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Notification

logger = logging.getLogger(__name__)


def _admins():
    User = get_user_model()
    return list(User.objects.filter(is_staff=True, is_active=True))


def _client_user(client):
    user = getattr(client, "user", None) if client is not None else None
    return user if user is not None and user.is_active else None


def notify(recipients, kind, title, body="", portfolio=None, actor=None):
    """
    Har recipient ke liye ek Notification (duplicates aur actor ko chor kar).
    Return: kitni rows bani. Error bahar nahi phenktay (log hota hai) taake asal action na ruke.
    """
    try:
        seen, rows = set(), []
        for user in recipients:
            if user is None or user.pk in seen:
                continue
            seen.add(user.pk)
            if actor is not None and user.pk == actor.pk:
                continue
            rows.append(Notification(
                recipient=user, kind=kind, title=title[:255], body=body,
                portfolio=portfolio,
                portfolio_title=(portfolio.title if portfolio is not None else "")[:255],
            ))
        if rows:
            with transaction.atomic():
                Notification.objects.bulk_create(rows)
        return len(rows)
    except Exception:  # noqa: BLE001
        logger.exception("Could not create notification (%s)", kind)
        return 0


def notify_portal_welcome(client):
    """Invite accept karne par client ko welcome notification."""
    return notify(
        [_client_user(client)],
        Notification.PORTAL_WELCOME,
        "Welcome to your portal",
        "Your account is ready. You can now create and manage your portfolios.",
    )


def notify_portfolio_event(portfolio, kind, actor):
    """portfolio_created / _deleted / _published / _unpublished."""
    actor_is_client = actor is not None and not actor.is_staff
    client = portfolio.client
    who = client.full_name
    verbs = {
        Notification.PORTFOLIO_CREATED: ("New portfolio created", f"{who} created the portfolio '{portfolio.title}'."),
        Notification.PORTFOLIO_DELETED: ("Portfolio deleted", f"{who} deleted the portfolio '{portfolio.title}'."),
        Notification.PORTFOLIO_PUBLISHED: ("Portfolio published", f"The portfolio '{portfolio.title}' was published."),
        Notification.PORTFOLIO_UNPUBLISHED: ("Portfolio unpublished", f"The portfolio '{portfolio.title}' was unpublished."),
    }
    title, body = verbs[kind]

    if kind in (Notification.PORTFOLIO_CREATED, Notification.PORTFOLIO_DELETED):
        recipients = _admins() if actor_is_client else []
    else:
        recipients = _admins() if actor_is_client else [_client_user(client)]
    notify(recipients, kind, title, body, portfolio=portfolio, actor=actor)


def notify_contact_message(message):
    """Public contact form se aaya message -> us portfolio ke client ko."""
    portfolio = message.portfolio
    notify(
        [_client_user(portfolio.client)],
        Notification.CONTACT_MESSAGE,
        f"New message from {message.full_name}",
        message.subject,
        portfolio=portfolio,
    )


def notify_portal_activated(client, actor=None):
    """Client ne invite accept kar ke portal activate kiya -> saare admins ko."""
    notify(
        _admins(),
        Notification.PORTAL_ACTIVATED,
        f"{client.full_name} activated their portal",
        "The client accepted the invite and set a password.",
        actor=actor,
    )

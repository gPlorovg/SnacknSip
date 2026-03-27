import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.api.models import EventGuest, GuestLimitUsage
from apps.api.models.events import StallStaff
from apps.api.models.orders import OrderStatus
from apps.api.auth.tokens import get_tokens_for_event_user
from apps.api.tests.factories import (
    EventUserFactory,
    GuestRoleFactory,
    GuestRoleItemFactory,
    MenuItemFactory,
    StallFactory,
)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def setup_data():
    stall = StallFactory()
    event = stall.event
    menu = stall.menu
    item1 = MenuItemFactory(menu=menu, name="Coffee", price=200)
    item2 = MenuItemFactory(menu=menu, name="Bun", price=150)

    role = GuestRoleFactory(event=event)
    GuestRoleItemFactory(role=role, menu_item=item1, max_quantity=2)
    GuestRoleItemFactory(role=role, menu_item=item2, max_quantity=1)

    guest_user = EventUserFactory.create_guest(event=event)
    guest_profile, _ = EventGuest.objects.get_or_create(
        event=event, event_user=guest_user
    )
    guest_profile.role = role
    guest_profile.save()

    return {
        "event": event,
        "stall": stall,
        "item1": item1,
        "item2": item2,
        "guest_user": guest_user,
        "guest_profile": guest_profile,
    }


@pytest.mark.django_db
def test_guest_can_order_within_limits(client, setup_data):
    guest = setup_data["guest_user"]
    stall = setup_data["stall"]
    item1 = setup_data["item1"]

    # Auth
    tokens = get_tokens_for_event_user(guest, setup_data["event"])
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    url = reverse("order-list")
    payload = {
        "stall_id": stall.id,
        "items": [{"menu_item_id": item1.id, "quantity": 1}],
    }

    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    usage = GuestLimitUsage.objects.get(
        event_guest=setup_data["guest_profile"], menu_item=item1
    )
    assert usage.used_quantity == 1


@pytest.mark.django_db
def test_guest_cannot_exceed_limit(client, setup_data):
    guest = setup_data["guest_user"]
    stall = setup_data["stall"]
    item1 = setup_data["item1"]

    tokens = get_tokens_for_event_user(guest, setup_data["event"])
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    url = reverse("order-list")
    payload = {
        "stall_id": stall.id,
        "items": [
            {"menu_item_id": item1.id, "quantity": 3}  # Limit is 2
        ],
    }

    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "доступно" in str(response.data).lower()
        or "запрошено" in str(response.data).lower()
    )


@pytest.mark.django_db
def test_limit_returned_on_cancel(client, setup_data):
    # Setup - Make valid order
    guest = setup_data["guest_user"]
    stall = setup_data["stall"]
    item1 = setup_data["item1"]

    tokens = get_tokens_for_event_user(guest, setup_data["event"])
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    payload = {
        "stall_id": stall.id,
        "items": [{"menu_item_id": item1.id, "quantity": 2}],
    }
    resp = client.post(reverse("order-list"), payload, format="json")
    order_id = resp.data["id"]

    # Limit used
    usage = GuestLimitUsage.objects.get(
        event_guest=setup_data["guest_profile"], menu_item=item1
    )
    assert usage.used_quantity == 2

    # Staff cancels order
    staff_user = EventUserFactory.create_staff(event=stall.event)
    StallStaff.objects.create(event_user=staff_user, stall=stall)

    staff_token = get_tokens_for_event_user(staff_user, setup_data["event"])
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {staff_token['access']}")

    patch_url = reverse("staff-order-update", kwargs={"pk": order_id})
    patch_resp = client.patch(
        patch_url, {"status": OrderStatus.CANCELLED}, format="json"
    )
    assert patch_resp.status_code == status.HTTP_200_OK

    # Limit returned
    usage.refresh_from_db()
    assert usage.used_quantity == 0

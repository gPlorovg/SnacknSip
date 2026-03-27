import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.api.models import EventGuest, GuestLimitUsage, Order
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

    role = GuestRoleFactory(event=event)
    GuestRoleItemFactory(role=role, menu_item=item1, max_quantity=2)

    guest_user = EventUserFactory.create_guest(event=event)
    guest_profile, _ = EventGuest.objects.get_or_create(
        event=event, event_user=guest_user
    )
    guest_profile.role = role
    guest_profile.save()

    staff_user = EventUserFactory.create_staff(event=stall.event)
    StallStaff.objects.create(event_user=staff_user, stall=stall)

    return {
        "event": event,
        "stall": stall,
        "item1": item1,
        "guest_user": guest_user,
        "guest_profile": guest_profile,
        "staff_user": staff_user,
    }


@pytest.mark.django_db
def test_stop_list_cancels_order_and_returns_limit(client, setup_data):
    guest = setup_data["guest_user"]
    stall = setup_data["stall"]
    item1 = setup_data["item1"]
    staff = setup_data["staff_user"]

    # 1. Guest creates order
    tokens = get_tokens_for_event_user(guest, setup_data["event"])
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    payload = {
        "stall_id": stall.id,
        "items": [{"menu_item_id": item1.id, "quantity": 1}],
    }
    resp = client.post(reverse("order-list"), payload, format="json")
    order_id = resp.data["id"]

    # Limit used
    usage = GuestLimitUsage.objects.get(
        event_guest=setup_data["guest_profile"], menu_item=item1
    )
    assert usage.used_quantity == 1

    # 2. Staff turns off item1 availability
    staff_token = get_tokens_for_event_user(staff, setup_data["event"])
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {staff_token['access']}")

    patch_url = reverse("staff-menu-toggle", kwargs={"item_id": item1.id})
    patch_resp = client.patch(patch_url, {"is_available": False}, format="json")

    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.data["is_available"] is False

    # 3. Order is cancelled because it only had item1
    order = Order.objects.get(pk=order_id)
    assert order.status == OrderStatus.CANCELLED
    assert "стоп-лист" in order.cancel_note

    # 4. Limit returned
    usage.refresh_from_db()
    assert usage.used_quantity == 0

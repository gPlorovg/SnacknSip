import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.api.models import EventGuest, Order
from apps.api.models.events import StallStaff
from apps.api.models.orders import OrderStatus
from apps.api.auth.tokens import get_tokens_for_event_user
from apps.api.tests.factories import (
    EventFactory,
    EventUserFactory,
    GuestRoleFactory,
    GuestRoleItemFactory,
    MenuFactory,
    MenuItemFactory,
    StallFactory,
)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def setup_data():
    event = EventFactory()
    menu = MenuFactory(event=event)
    item1 = MenuItemFactory(menu=menu, name="Coffee")

    stall_close = StallFactory(event=event, menu=menu, name="Stall A")
    stall_open = StallFactory(event=event, menu=menu, name="Stall B")

    role = GuestRoleFactory(event=event)
    GuestRoleItemFactory(role=role, menu_item=item1, max_quantity=2)

    guest_user = EventUserFactory.create_guest(event=event)
    guest_profile, _ = EventGuest.objects.get_or_create(
        event=event, event_user=guest_user
    )
    guest_profile.role = role
    guest_profile.save()

    staff_user_close = EventUserFactory.create_staff(event=event)
    StallStaff.objects.create(event_user=staff_user_close, stall=stall_close)

    return {
        "event": event,
        "stall_close": stall_close,
        "stall_open": stall_open,
        "item1": item1,
        "guest_user": guest_user,
        "staff_close": staff_user_close,
    }


@pytest.mark.django_db
def test_auto_redistribution_moves_order_to_open_stall(client, setup_data):
    guest = setup_data["guest_user"]
    stall_close = setup_data["stall_close"]
    stall_open = setup_data["stall_open"]
    item1 = setup_data["item1"]

    # 1. Guest creates order on Stall A
    tokens = get_tokens_for_event_user(guest, setup_data["event"])
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    payload = {
        "stall_id": stall_close.id,
        "items": [{"menu_item_id": item1.id, "quantity": 1}],
    }
    resp = client.post(reverse("order-list"), payload, format="json")
    order_id = resp.data["id"]

    # 2. Staff A auto-redistributes
    staff = setup_data["staff_close"]
    staff_token = get_tokens_for_event_user(staff, setup_data["event"])
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {staff_token['access']}")

    redist_url = reverse("staff-auto-redistribute")
    redist_resp = client.post(redist_url, format="json")

    assert redist_resp.status_code == status.HTTP_200_OK

    # 3. Order is moved to Stall B
    order = Order.objects.get(pk=order_id)
    assert order.stall == stall_open
    assert order.status == OrderStatus.CREATED

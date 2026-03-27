import pytest

from apps.api.models import EventUser, StallMenuItem
from apps.api.tests.factories import (
    EventFactory,
    MenuFactory,
    MenuItemFactory,
    StallFactory,
)


@pytest.mark.django_db
def test_stall_auto_creates_stall_menu_items():
    event = EventFactory()
    menu = MenuFactory(event=event)
    item1 = MenuItemFactory(menu=menu)
    item2 = MenuItemFactory(menu=menu)

    # When a stall is created and assigned this menu
    stall = StallFactory(event=event, menu=menu)

    # Then StallMenuItem records should be auto-created
    stall_items = StallMenuItem.objects.filter(stall=stall)
    assert stall_items.count() == 2
    assert {si.menu_item for si in stall_items} == {item1, item2}


@pytest.mark.django_db
def test_menu_item_auto_adds_to_stalls():
    event = EventFactory()
    menu = MenuFactory(event=event)
    # create stall first
    stall = StallFactory(event=event, menu=menu)

    # When a new item is added to the menu
    new_item = MenuItemFactory(menu=menu)

    # Then the stall should get the new item automatically
    assert StallMenuItem.objects.filter(stall=stall, menu_item=new_item).exists()


@pytest.mark.django_db
def test_event_user_telegram_username_normalized():
    event = EventFactory()
    user = EventUser(
        event=event,
        login="test@example.com",
        name="Test",
        telegram_username="@testuser",
        role=EventUser.Role.GUEST,
    )
    user.save()

    assert user.telegram_username == "testuser"

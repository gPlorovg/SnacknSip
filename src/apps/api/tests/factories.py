import factory
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.api.models import (
    Event,
    EventUser,
    Menu,
    MenuItem,
    Order,
    OrderItem,
    Stall,
)
from apps.api.models.guest_roles import GuestRole, GuestRoleItem
from apps.api.models.orders import OrderStatus
from apps.api.models.stalls import StallStatus
import faker

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    is_staff = False
    is_active = True


class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Event

    name = factory.Faker("company")
    organizer = factory.SubFactory(UserFactory)
    start_time = factory.LazyFunction(timezone.now)
    end_time = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(days=1))
    is_open = True


fake = faker.Faker()


class EventUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EventUser

    event = factory.SubFactory(EventFactory)
    name = factory.Faker("name")
    login = factory.Sequence(lambda n: f"user{n}@example.com")
    role = EventUser.Role.GUEST

    @classmethod
    def create_guest(cls, event, login=None, telegram_username=None):
        name = fake.name()
        user, plain_password = EventUser.create_with_password(
            event=event,
            login=login or f"guest_{fake.uuid4()}@example.com",
            name=name,
            role=EventUser.Role.GUEST,
        )
        if telegram_username:
            user.telegram_username = telegram_username
            user.save(update_fields=["telegram_username"])
        return user

    @classmethod
    def create_staff(cls, event, login=None):
        name = fake.name()
        user, plain_password = EventUser.create_with_password(
            event=event,
            login=login or f"staff_{fake.uuid4()}@example.com",
            name=name,
            role=EventUser.Role.STAFF,
        )
        return user


class MenuFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Menu

    event = factory.SubFactory(EventFactory)
    name = factory.Sequence(lambda n: f"Menu {n}")


class MenuItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuItem

    menu = factory.SubFactory(MenuFactory)
    name = factory.Sequence(lambda n: f"Item {n}")
    price = 100


class StallFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Stall

    event = factory.SubFactory(EventFactory)
    name = factory.Sequence(lambda n: f"Stall {n}")
    abbr = factory.Sequence(lambda n: f"S{n}")
    menu = factory.SubFactory(MenuFactory, event=factory.SelfAttribute("..event"))
    status = StallStatus.OPEN


class GuestRoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GuestRole

    event = factory.SubFactory(EventFactory)
    name = factory.Sequence(lambda n: f"Role {n}")


class GuestRoleItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GuestRoleItem

    role = factory.SubFactory(GuestRoleFactory)
    menu_item = factory.SubFactory(MenuItemFactory)
    max_quantity = 5
    discount_pct = 100


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    event = factory.SubFactory(EventFactory)
    guest = factory.SubFactory(EventUserFactory)
    stall = factory.SubFactory(StallFactory, event=factory.SelfAttribute("..event"))
    status = OrderStatus.CREATED


class OrderItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    menu_item = factory.SubFactory(MenuItemFactory)
    quantity = 1
    price = 100
    discount_pct = 100

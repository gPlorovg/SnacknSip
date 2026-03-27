"""Organizer-facing API views."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.auth.permissions import IsOrganizer
from apps.api.models import Event, EventGuest, Menu, MenuItem, Order, Stall
from apps.api.models.guest_roles import GuestRole, GuestRoleItem
from apps.api.models.users import EventUser
from apps.api.serializers.organizer import (
    AssignRoleSerializer,
    BlockUserSerializer,
    EventCreateSerializer,
    EventSerializer,
    EventUserCreateSerializer,
    EventUserDetailSerializer,
    EventUserListSerializer,
    GuestRoleCreateSerializer,
    GuestRoleItemSerializer,
    GuestRoleSerializer,
    MenuCreateSerializer,
    MenuItemSerializer,
    MenuSerializer,
    OrgOrderSerializer,
    OrgStallCreateSerializer,
    OrgStallSerializer,
)


def _get_event(request, event_id):
    """Return an event owned by the organizer."""
    try:
        return Event.objects.get(pk=event_id, organizer=request.user)
    except Event.DoesNotExist:
        return None


# ─────────────────────────────────────────────────────
# Events
# ─────────────────────────────────────────────────────


@extend_schema(tags=["Organizer — Events"])
class EventListView(APIView):
    permission_classes = [IsOrganizer]

    @extend_schema(
        summary="Мои мероприятия", responses={200: EventSerializer(many=True)}
    )
    def get(self, request):
        events = Event.objects.filter(organizer=request.user).order_by("-created_at")
        return Response(EventSerializer(events, many=True).data)

    @extend_schema(
        summary="Создать мероприятие",
        request=EventCreateSerializer,
        responses={201: EventSerializer},
    )
    def post(self, request):
        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = Event.objects.create(
            organizer=request.user, **serializer.validated_data
        )
        return Response(EventSerializer(event).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Organizer — Events"])
class EventDetailView(APIView):
    permission_classes = [IsOrganizer]

    @extend_schema(summary="Детали мероприятия", responses={200: EventSerializer})
    def get(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response(
                {"detail": "Мероприятие не найдено."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(EventSerializer(event).data)

    @extend_schema(
        summary="Обновить мероприятие",
        request=EventCreateSerializer,
        responses={200: EventSerializer},
    )
    def patch(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response(
                {"detail": "Мероприятие не найдено."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = EventCreateSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(EventSerializer(event).data)


@extend_schema(tags=["Organizer — Events"], summary="Открыть мероприятие")
class OpenEventView(APIView):
    permission_classes = [IsOrganizer]

    def post(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        event.open()
        return Response(EventSerializer(event).data)


@extend_schema(tags=["Organizer — Events"], summary="Закрыть мероприятие")
class CloseEventView(APIView):
    permission_classes = [IsOrganizer]

    def post(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        event.close()
        return Response(EventSerializer(event).data)


# ─────────────────────────────────────────────────────
# Stalls
# ─────────────────────────────────────────────────────


@extend_schema(tags=["Organizer — Stalls"])
class OrgStallListView(APIView):
    permission_classes = [IsOrganizer]

    @extend_schema(
        summary="Точки мероприятия", responses={200: OrgStallSerializer(many=True)}
    )
    def get(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        stalls = Stall.objects.filter(event=event)
        return Response(OrgStallSerializer(stalls, many=True).data)

    @extend_schema(
        summary="Создать точку",
        request=OrgStallCreateSerializer,
        responses={201: OrgStallSerializer},
    )
    def post(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        serializer = OrgStallCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stall = Stall.objects.create(event=event, **serializer.validated_data)
        return Response(OrgStallSerializer(stall).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Organizer — Stalls"])
class OrgStallDetailView(APIView):
    permission_classes = [IsOrganizer]

    def _get(self, request, event_id, stall_id):
        event = _get_event(request, event_id)
        if not event:
            return None
        try:
            return Stall.objects.get(pk=stall_id, event=event)
        except Stall.DoesNotExist:
            return None

    @extend_schema(summary="Детали точки", responses={200: OrgStallSerializer})
    def get(self, request, event_id, stall_id):
        stall = self._get(request, event_id, stall_id)
        if not stall:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrgStallSerializer(stall).data)

    @extend_schema(
        summary="Обновить точку",
        request=OrgStallSerializer,
        responses={200: OrgStallSerializer},
    )
    def patch(self, request, event_id, stall_id):
        stall = self._get(request, event_id, stall_id)
        if not stall:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        serializer = OrgStallSerializer(stall, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrgStallSerializer(stall).data)

    @extend_schema(summary="Удалить точку")
    def delete(self, request, event_id, stall_id):
        stall = self._get(request, event_id, stall_id)
        if not stall:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        stall.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────────────
# Menus
# ─────────────────────────────────────────────────────


@extend_schema(tags=["Organizer — Menus"])
class OrgMenuListView(APIView):
    permission_classes = [IsOrganizer]

    @extend_schema(
        summary="Меню мероприятия", responses={200: MenuSerializer(many=True)}
    )
    def get(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        menus = Menu.objects.filter(event=event).prefetch_related("items")
        return Response(MenuSerializer(menus, many=True).data)

    @extend_schema(
        summary="Создать меню",
        request=MenuCreateSerializer,
        responses={201: MenuSerializer},
    )
    def post(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        serializer = MenuCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        menu = Menu.objects.create(event=event, **serializer.validated_data)
        return Response(MenuSerializer(menu).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Organizer — Menus"])
class OrgMenuItemListView(APIView):
    permission_classes = [IsOrganizer]

    def _get_menu(self, request, event_id, menu_id):
        event = _get_event(request, event_id)
        if not event:
            return None
        try:
            return Menu.objects.get(pk=menu_id, event=event)
        except Menu.DoesNotExist:
            return None

    @extend_schema(
        summary="Добавить позицию в меню",
        request=MenuItemSerializer,
        responses={201: MenuItemSerializer},
    )
    def post(self, request, event_id, menu_id):
        menu = self._get_menu(request, event_id, menu_id)
        if not menu:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        serializer = MenuItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = MenuItem.objects.create(menu=menu, **serializer.validated_data)
        return Response(MenuItemSerializer(item).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Organizer — Menus"])
class OrgMenuItemDetailView(APIView):
    permission_classes = [IsOrganizer]

    def _get_item(self, request, event_id, menu_id, item_id):
        event = _get_event(request, event_id)
        if not event:
            return None
        try:
            return MenuItem.objects.get(pk=item_id, menu_id=menu_id, menu__event=event)
        except MenuItem.DoesNotExist:
            return None

    @extend_schema(
        summary="Обновить позицию меню",
        request=MenuItemSerializer,
        responses={200: MenuItemSerializer},
    )
    def patch(self, request, event_id, menu_id, item_id):
        item = self._get_item(request, event_id, menu_id, item_id)
        if not item:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        serializer = MenuItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MenuItemSerializer(item).data)

    @extend_schema(summary="Удалить позицию меню")
    def delete(self, request, event_id, menu_id, item_id):
        item = self._get_item(request, event_id, menu_id, item_id)
        if not item:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────


@extend_schema(tags=["Organizer — Users"])
class OrgUserListView(APIView):
    permission_classes = [IsOrganizer]

    @extend_schema(
        summary="Пользователи мероприятия",
        responses={200: EventUserListSerializer(many=True)},
    )
    def get(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        users = EventUser.objects.filter(event=event)
        return Response(EventUserListSerializer(users, many=True).data)

    @extend_schema(
        summary="Создать пользователя",
        request=EventUserCreateSerializer,
        responses={201: EventUserDetailSerializer},
    )
    def post(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EventUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        login = data.get("login")
        telegram_username = data.get("telegram_username")
        name = data["name"]
        role = data["role"]

        if login:
            user, plain = EventUser.create_with_password(
                event=event, login=login, name=name, role=role
            )
            if telegram_username:
                user.telegram_username = telegram_username
                user.save(update_fields=["telegram_username"])
        else:
            user = EventUser.objects.create(
                event=event,
                telegram_username=telegram_username,
                name=name,
                role=role,
            )

        return Response(
            EventUserDetailSerializer(user).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["Organizer — Users"])
class OrgUserDetailView(APIView):
    permission_classes = [IsOrganizer]

    def _get_user(self, request, event_id, user_id):
        event = _get_event(request, event_id)
        if not event:
            return None
        try:
            return EventUser.objects.get(pk=user_id, event=event)
        except EventUser.DoesNotExist:
            return None

    @extend_schema(
        summary="Детали пользователя (включая пароль)",
        responses={200: EventUserDetailSerializer},
    )
    def get(self, request, event_id, user_id):
        user = self._get_user(request, event_id, user_id)
        if not user:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        return Response(EventUserDetailSerializer(user).data)

    @extend_schema(
        summary="Заблокировать / разблокировать пользователя",
        request=BlockUserSerializer,
        responses={200: EventUserListSerializer},
    )
    def patch(self, request, event_id, user_id):
        user = self._get_user(request, event_id, user_id)
        if not user:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        serializer = BlockUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.is_blocked = serializer.validated_data["is_blocked"]
        user.save(update_fields=["is_blocked"])
        return Response(EventUserListSerializer(user).data)

    @extend_schema(summary="Удалить пользователя из мероприятия")
    def delete(self, request, event_id, user_id):
        user = self._get_user(request, event_id, user_id)
        if not user:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────────────
# Guest Roles
# ─────────────────────────────────────────────────────


@extend_schema(tags=["Organizer — Roles"])
class OrgGuestRoleListView(APIView):
    permission_classes = [IsOrganizer]

    @extend_schema(
        summary="Роли гостей", responses={200: GuestRoleSerializer(many=True)}
    )
    def get(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        roles = GuestRole.objects.filter(event=event).prefetch_related("allowed_items")
        return Response(GuestRoleSerializer(roles, many=True).data)

    @extend_schema(
        summary="Создать роль",
        request=GuestRoleCreateSerializer,
        responses={201: GuestRoleSerializer},
    )
    def post(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        serializer = GuestRoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = GuestRole.objects.create(event=event, **serializer.validated_data)
        return Response(GuestRoleSerializer(role).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Organizer — Roles"],
    summary="Добавить позицию в роль",
    request=GuestRoleItemSerializer,
    responses={201: GuestRoleItemSerializer},
)
class OrgGuestRoleItemView(APIView):
    permission_classes = [IsOrganizer]

    def post(self, request, event_id, role_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        try:
            role = GuestRole.objects.get(pk=role_id, event=event)
        except GuestRole.DoesNotExist:
            return Response(
                {"detail": "Роль не найдена."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = GuestRoleItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = GuestRoleItem.objects.create(role=role, **serializer.validated_data)
        return Response(
            GuestRoleItemSerializer(item).data, status=status.HTTP_201_CREATED
        )


@extend_schema(
    tags=["Organizer — Roles"],
    summary="Назначить роль гостю",
    request=AssignRoleSerializer,
    responses={200: None},
)
class AssignGuestRoleView(APIView):
    permission_classes = [IsOrganizer]

    def post(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AssignRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            guest_user = EventUser.objects.get(
                pk=serializer.validated_data["guest_id"],
                event=event,
                role=EventUser.Role.GUEST,
            )
        except EventUser.DoesNotExist:
            return Response(
                {"detail": "Гость не найден."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            role = GuestRole.objects.get(
                pk=serializer.validated_data["role_id"], event=event
            )
        except GuestRole.DoesNotExist:
            return Response(
                {"detail": "Роль не найдена."}, status=status.HTTP_404_NOT_FOUND
            )

        guest_profile, _ = EventGuest.objects.get_or_create(
            event_user=guest_user, event=event
        )
        guest_profile.role = role
        guest_profile.save(update_fields=["role"])

        return Response(
            {"detail": f"Роль «{role.name}» назначена гостю {guest_user.name}."}
        )


# ─────────────────────────────────────────────────────
# Orders overview
# ─────────────────────────────────────────────────────


@extend_schema(tags=["Organizer — Orders"], summary="Все заказы мероприятия")
class OrgOrderListView(APIView):
    permission_classes = [IsOrganizer]

    def get(self, request, event_id):
        event = _get_event(request, event_id)
        if not event:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)

        orders = (
            Order.objects.filter(event=event)
            .select_related("guest", "stall")
            .prefetch_related("items__menu_item")
            .order_by("-created_at")
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            orders = orders.filter(status=status_filter)

        return Response(OrgOrderSerializer(orders, many=True).data)

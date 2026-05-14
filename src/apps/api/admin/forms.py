"""Forms used by the organizer-specific admin site."""

from __future__ import annotations

from django import forms

from apps.api.models import Event


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class BatchMenuImageUploadForm(forms.Form):
    """Assign one image per selected menu item."""

    item_ids = forms.CharField(widget=forms.HiddenInput)
    images = forms.FileField(
        label="Изображения",
        required=True,
        widget=MultiFileInput,
        help_text="Загрузите по одному файлу на каждую выбранную позицию меню.",
    )


class VisitorCsvImportForm(forms.Form):
    """CSV import form for event visitors (EventUser with guest/staff role)."""

    event = forms.ModelChoiceField(
        queryset=Event.objects.none(),
        label="Мероприятие",
        required=True,
    )
    csv_file = forms.FileField(label="CSV файл", required=True)
    dry_run = forms.BooleanField(
        required=False,
        initial=True,
        label="Только проверить (без сохранения)",
    )

    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop("organizer", None)
        super().__init__(*args, **kwargs)
        if organizer is not None:
            event_field = self.fields["event"]
            if isinstance(event_field, forms.ModelChoiceField):
                event_field.queryset = Event.objects.filter(
                    organizer=organizer
                ).order_by("-created_at")

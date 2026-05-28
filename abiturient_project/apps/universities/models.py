from django.db import models
from django.core.exceptions import ValidationError


def validate_image_size(image):
    max_mb = 2
    if image.size > max_mb * 1024 * 1024:
        raise ValidationError(f'Размер изображения не должен превышать {max_mb} МБ.')


class University(models.Model):
    name = models.CharField('Название', max_length=255)
    full_name = models.CharField('Полное название', max_length=512, blank=True)
    city = models.CharField('Город', max_length=100)
    region = models.CharField('Регион', max_length=150, blank=True)
    address = models.CharField('Адрес', max_length=255, blank=True)
    website = models.URLField('Сайт', blank=True)
    email = models.EmailField('Email', blank=True)
    phone = models.CharField('Телефон', max_length=50, blank=True)
    description = models.TextField('Описание', blank=True)
    photo = models.ImageField(
        'Фотография',
        upload_to='universities/',
        blank=True,
        null=True,
        validators=[validate_image_size],
        help_text='Максимальный размер: 2 МБ. Рекомендуемые форматы: JPG, PNG.'
    )
    has_dormitory = models.BooleanField('Общежитие', default=False)
    has_military = models.BooleanField('Военная кафедра', default=False)

    # ── Научная активность (данные из OpenAlex) ───────────────────────
    openalex_id    = models.CharField('OpenAlex ID', max_length=32, blank=True)
    works_count    = models.PositiveIntegerField('Публикаций', null=True, blank=True)
    cited_by_count = models.PositiveIntegerField('Цитирований', null=True, blank=True)
    h_index        = models.PositiveIntegerField('Индекс Хирша', null=True, blank=True)


    class Meta:
        verbose_name = 'Университет'
        verbose_name_plural = 'Университеты'

    def __str__(self):
        return self.name


class AdmissionDeadline(models.Model):
    """Ключевые даты приёмной кампании конкретного университета."""

    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='deadlines',
        verbose_name='Университет'
    )

    date = models.CharField('Дата', max_length=50)
    event = models.CharField('Событие', max_length=255)
    type = models.CharField('Тип', max_length=50, default='Дедлайн')
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Дата приёмной кампании'
        verbose_name_plural = 'Даты приёмной кампании'
        ordering = ['order']

    def __str__(self):
        return f'{self.university.name}: {self.date} — {self.event}'
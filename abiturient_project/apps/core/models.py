from django.db import models


# class AdmissionDeadline(models.Model):
#     """Ключевые даты приёмной кампании."""
#     date = models.CharField('Дата', max_length=50)
#     event = models.CharField('Событие', max_length=255)
#     type = models.CharField('Тип', max_length=50, default='Дедлайн')
#     order = models.PositiveIntegerField('Порядок', default=0)

#     class Meta:
#         verbose_name = 'Дата приёмной кампании'
#         verbose_name_plural = 'Даты приёмной кампании'
#         ordering = ['order']

#     def __str__(self):
#         return f'{self.date} — {self.event}'


class AdmissionStep(models.Model):
    """Этапы поступления."""
    title = models.CharField('Заголовок', max_length=100)
    desc = models.TextField('Описание')
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Этап поступления'
        verbose_name_plural = 'Этапы поступления'
        ordering = ['order']

    def __str__(self):
        return self.title


class RequiredDocument(models.Model):
    """Документы для поступления."""
    TYPE_CHOICES = [
        ('required', 'Обязательный'),
        ('optional', 'Дополнительный'),
    ]
    text = models.CharField('Документ', max_length=255)
    type = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES, default='required')
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Документ'
        verbose_name_plural = 'Документы'
        ordering = ['order']

    def __str__(self):
        return self.text


class BudgetCategory(models.Model):
    """Категории бюджетных мест."""
    title = models.CharField('Название', max_length=100)
    desc = models.CharField('Описание', max_length=255)
    quota = models.CharField('Квота', max_length=50)
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Категория мест'
        verbose_name_plural = 'Категории мест'
        ordering = ['order']

    def __str__(self):
        return self.title


class Benefit(models.Model):
    """Льготники."""
    text = models.CharField('Категория льготников', max_length=255)
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Льготник'
        verbose_name_plural = 'Льготники'
        ordering = ['order']

    def __str__(self):
        return self.text


class FAQ(models.Model):
    """Часто задаваемые вопросы."""
    SECTION_CHOICES = [
        ('home', 'Главная страница'),
        ('guide', 'Справочник'),
    ]
    question = models.CharField('Вопрос', max_length=255)
    answer = models.TextField('Ответ')
    section = models.CharField('Раздел', max_length=20,
                               choices=SECTION_CHOICES, default='guide')
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Вопрос и ответ'
        verbose_name_plural = 'Вопросы и ответы'
        ordering = ['order']

    def __str__(self):
        return self.question
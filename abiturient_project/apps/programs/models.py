from django.db import models
from apps.universities.models import University
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

class Subject(models.Model):
    name = models.CharField('Предмет', max_length=100)

    class Meta:
        verbose_name = 'Предмет ЕГЭ'
        verbose_name_plural = 'Предметы ЕГЭ'

    def __str__(self):
        return self.name


class Program(models.Model):
    PROFILE_CHOICES = [
        ('IT', 'IT'),
        ('Наука', 'Наука'),
        ('Техника', 'Техника'),
        ('Экономика', 'Экономика'),
        ('Гуманитарные', 'Гуманитарные'),
    ]

    DEGREE_CHOICES = [
        ('bachelor', 'Бакалавриат'),
        ('master', 'Магистратура'),
        ('specialist', 'Специалитет'),
        ('college', 'Среднее профессиональное'),
    ]

    STUDY_FORM_CHOICES = [
        ('full_time', 'Очная'),
        ('part_time', 'Заочная'),
        ('evening', 'Очно-заочная'),
    ]

    university = models.ForeignKey(
        University, on_delete=models.CASCADE,
        related_name='programs', verbose_name='Университет'
    )
    name = models.CharField('Название', max_length=255)
    code = models.CharField('Код специальности', max_length=20)
    faculty = models.CharField('Факультет', max_length=255)
    profile = models.CharField('Профиль', max_length=50, choices=PROFILE_CHOICES)
    degree = models.CharField('Уровень подготовки', max_length=20,
                              choices=DEGREE_CHOICES, default='bachelor')
    study_form = models.CharField('Форма обучения', max_length=20,
                                  choices=STUDY_FORM_CHOICES, default='full_time')
    # min_score = models.PositiveIntegerField('Минимальный балл')
    # avg_score = models.PositiveIntegerField('Средний балл')
    # budget_places = models.PositiveIntegerField('Бюджетных мест')
    # paid_places = models.PositiveIntegerField('Платных мест', default=0)
    # cost_per_year = models.PositiveIntegerField('Стоимость в год (руб.)')
    years = models.PositiveSmallIntegerField('Срок обучения', default=4)
    description = models.TextField('Описание', blank=True)
    subjects = models.ManyToManyField(
        'Subject',
        through='ProgramSubject',
        related_name='programs',
        verbose_name='Предметы ЕГЭ'
    )

    class Meta:
        verbose_name = 'Программа'
        verbose_name_plural = 'Программы'

    def __str__(self):
        return self.name

    def get_degree_display_short(self):
        return dict(self.DEGREE_CHOICES).get(self.degree, '')

    def get_study_form_display_short(self):
        return dict(self.STUDY_FORM_CHOICES).get(self.study_form, '')
    
    @property
    def current_plan(self):
        return self.admission_plans.order_by('-year').first()

    @property
    def min_score(self):
        plan = self.current_plan
        return plan.min_score if plan else None

    @property
    def avg_score(self):
        plan = self.current_plan
        return plan.avg_score if plan else None

    @property
    def budget_places(self):
        plan = self.current_plan
        return plan.budget_places if plan else 0

    @property
    def paid_places(self):
        plan = self.current_plan
        return plan.paid_places if plan else 0

    @property
    def cost_per_year(self):
        plan = self.current_plan
        return plan.cost_per_year if plan else 0

class ProgramSubject(models.Model):
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name='program_subjects',
        verbose_name='Программа'
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='program_subjects',
        verbose_name='Предмет'
    )

    is_required = models.BooleanField(
        'Обязательный предмет',
        default=True
    )

    min_subject_score = models.PositiveIntegerField(
        'Минимальный балл по предмету',
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    group_number = models.PositiveSmallIntegerField(
        'Номер группы',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'Предмет программы'
        verbose_name_plural = 'Предметы программ'
        constraints = [
            models.UniqueConstraint(
                fields=['program', 'subject'],
                name='unique_program_subject'
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(min_subject_score__gte=0) &
                    models.Q(min_subject_score__lte=100)
                ) | models.Q(min_subject_score__isnull=True),
                name='program_subject_score_between_0_100'
            )]

    def __str__(self):
        return f'{self.program.name} — {self.subject.name}'

class AdmissionPlan(models.Model):
    program = models.ForeignKey(
        'Program',
        on_delete=models.CASCADE,
        related_name='admission_plans',
        verbose_name='Программа'
    )
    
    year = models.PositiveSmallIntegerField(
        'Год приёма',
        validators=[MinValueValidator(1)]
    )

    min_score = models.PositiveIntegerField(
        'Минимальный балл',
        null=True,
        blank=True
    )

    avg_score = models.PositiveIntegerField(
        'Средний балл',
        null=True,
        blank=True
    )

    budget_places = models.PositiveIntegerField(
        'Бюджетные места',
        default=0,
        validators=[MinValueValidator(0)]
    )

    paid_places = models.PositiveIntegerField(
        'Платные места',
        default=0,
        validators=[MinValueValidator(0)]
    )

    cost_per_year = models.PositiveIntegerField(
        'Стоимость обучения в год',
        default=0,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = 'План приёма'
        verbose_name_plural = 'Планы приёма'
        ordering = ['-year']
        constraints = [
            models.UniqueConstraint(
                fields=['program', 'year'],
                name='unique_program_admission_year'
            ),
            models.CheckConstraint(
                condition=models.Q(year__gt=0),
                name='admission_year_positive'
            ),
            models.CheckConstraint(
                condition=models.Q(budget_places__gte=0),
                name='admission_budget_places_non_negative'
            ),
            models.CheckConstraint(
                condition=models.Q(paid_places__gte=0),
                name='admission_paid_places_non_negative'
            ),
            models.CheckConstraint(
                condition=models.Q(cost_per_year__gte=0),
                name='admission_cost_non_negative'
            ),
        ]

    def __str__(self):
        return f'{self.program.name} — {self.year}'
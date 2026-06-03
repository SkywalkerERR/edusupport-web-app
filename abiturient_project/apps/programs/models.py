from django.db import models
from apps.universities.models import University
from django.core.validators import MinValueValidator, MaxValueValidator


class Faculty(models.Model):
    """Институт / Высшая школа / Факультет."""
    TYPE_CHOICES = [
        ('institute', 'Институт'),
        ('faculty',   'Факультет'),
        ('school',    'Высшая школа'),
        ('other',     'Другое'),
    ]
    university = models.ForeignKey(
        University, on_delete=models.CASCADE,
        related_name='faculties', verbose_name='Университет'
    )
    name       = models.CharField('Название', max_length=255)
    short_name = models.CharField('Краткое название', max_length=50, blank=True)
    type       = models.CharField('Тип', max_length=20,
                                  choices=TYPE_CHOICES, default='faculty')

    class Meta:
        verbose_name = 'Институт/Факультет'
        verbose_name_plural = 'Институты и факультеты'
        ordering = ['name']

    def __str__(self):
        return f'{self.get_type_display()} «{self.name}»'


class Department(models.Model):
    """Кафедра."""
    faculty = models.ForeignKey(
        Faculty, on_delete=models.CASCADE,
        related_name='departments', verbose_name='Институт/Факультет'
    )
    name = models.CharField('Название кафедры', max_length=255)

    class Meta:
        verbose_name = 'Кафедра'
        verbose_name_plural = 'Кафедры'
        ordering = ['name']

    def __str__(self):
        return self.name


class Direction(models.Model):
    """Направление подготовки."""
    faculty = models.ForeignKey(
        Faculty, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='directions', verbose_name='Институт/Факультет'
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='directions', verbose_name='Кафедра'
    )
    name = models.CharField('Название направления', max_length=255)
    code = models.CharField('Код направления', max_length=20, blank=True)

    class Meta:
        verbose_name = 'Направление подготовки'
        verbose_name_plural = 'Направления подготовки'
        ordering = ['code', 'name']

    def __str__(self):
        prefix = f'{self.code} ' if self.code else ''
        return f'{prefix}{self.name}'


class Subject(models.Model):
    name = models.CharField('Предмет', max_length=100)

    class Meta:
        verbose_name = 'Предмет ЕГЭ'
        verbose_name_plural = 'Предметы ЕГЭ'

    def __str__(self):
        return self.name


class Program(models.Model):
    DEGREE_CHOICES = [
        ('bachelor',     'Бакалавриат'),
        ('master',       'Магистратура'),
        ('specialist',   'Специалитет'),
        ('postgraduate', 'Аспирантура'),
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
    direction = models.ForeignKey(
        Direction, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='programs', verbose_name='Направление подготовки'
    )
    name = models.CharField('Название', max_length=255)
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
        verbose_name='Предметы ЕГЭ',
        blank=True,
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
    def required_program_subjects(self):
        return [ps for ps in self.program_subjects.all() if ps.is_required]

    @property
    def elective_program_subjects(self):
        return [ps for ps in self.program_subjects.all() if not ps.is_required]

    @property
    def direction_faculty(self):
        """Институт/Факультет: сначала прямая связь direction.faculty, затем через кафедру."""
        if not self.direction:
            return None
        return (
            self.direction.faculty
            or (self.direction.department and self.direction.department.faculty)
        )

    @property
    def current_plan(self):
        return self.admission_plans.order_by('-year').first()

    @property
    def min_score(self):
        """
        Минимальная сумма баллов (порог) по формуле:
        сумма min_subject_score обязательных предметов
        + минимальный min_subject_score среди необязательных предметов.
        Предметы без min_subject_score не учитываются.
        Возвращает None, если данных недостаточно.
        """
        ps_qs = self.program_subjects.all()
        required_scores = [
            ps.min_subject_score
            for ps in ps_qs
            if ps.is_required and ps.min_subject_score is not None
        ]
        elective_scores = [
            ps.min_subject_score
            for ps in ps_qs
            if not ps.is_required and ps.min_subject_score is not None
        ]
        if not required_scores and not elective_scores:
            return None
        total = sum(required_scores)
        if elective_scores:
            total += min(elective_scores)
        return total

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

    @property
    def passing_score_budget(self):
        plan = self.current_plan
        return plan.passing_score_budget if plan else None

    @property
    def passing_score_paid(self):
        plan = self.current_plan
        return plan.passing_score_paid if plan else None

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


class EntranceExam(models.Model):
    """Вступительное испытание (внутренний экзамен университета)."""
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name='entrance_exams',
        verbose_name='Программа'
    )
    name = models.CharField('Название испытания', max_length=255)
    min_score = models.PositiveIntegerField(
        'Минимальный балл',
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    description = models.TextField('Описание', blank=True)

    class Meta:
        verbose_name = 'Вступительное испытание'
        verbose_name_plural = 'Вступительные испытания'

    def __str__(self):
        return f'{self.program.name} — {self.name}'


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

    budget_places = models.PositiveIntegerField(
        'Бюджетные места',
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )

    paid_places = models.PositiveIntegerField(
        'Платные места',
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )

    cost_per_year = models.PositiveIntegerField(
        'Стоимость обучения в год',
        default=0,
        validators=[MinValueValidator(0)]
    )

    passing_score_budget = models.PositiveIntegerField(
        'Проходной балл (бюджет)',
        null=True,
        blank=True
    )

    passing_score_paid = models.PositiveIntegerField(
        'Проходной балл (контракт)',
        null=True,
        blank=True
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
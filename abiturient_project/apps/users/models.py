from django.db import models
from django.contrib.auth.models import User
from apps.programs.models import Program, Subject
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return f'Профиль {self.user.username}'

class ExamResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_results')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    score = models.PositiveIntegerField(
        'Балл',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        verbose_name = 'Результат ЕГЭ'
        verbose_name_plural = 'Результаты ЕГЭ'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'subject'],
                name='unique_user_subject_exam_result'
            ),
            models.CheckConstraint(
                condition=models.Q(score__gte=0) & models.Q(score__lte=100),
                name='exam_score_between_0_100'
            ),
        ]

    def __str__(self):
        return f'{self.user.username} — {self.subject.name}: {self.score}'

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    program = models.ForeignKey(Program, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Избранное'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'program'],
                name='unique_user_program_favorite'
            ),
        ]
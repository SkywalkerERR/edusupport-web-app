from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from apps.universities.models import University
from .models import Program, Subject, ProgramSubject
from .services import get_chance


class GetChanceTest(TestCase):
    """Проверка алгоритма расчёта шансов поступления."""

    def _make_program(self, min_score):
        """
        Создаёт программу с одним обязательным предметом,
        чей min_subject_score равен min_score.
        Program.min_score вернёт это значение.
        """
        uni = University.objects.create(name='Тест', city='Тест')
        p = Program.objects.create(
            university=uni, name='Прог',
            degree='bachelor', study_form='full_time',
        )
        subject = Subject.objects.create(name='Математика')
        ProgramSubject.objects.create(
            program=p, subject=subject,
            is_required=True, min_subject_score=min_score,
        )
        return p

    def test_high_chance(self):
        p = self._make_program(100)
        result = get_chance(135, p)
        self.assertEqual(result['css'], 'success')

    def test_good_chance(self):
        p = self._make_program(100)
        result = get_chance(115, p)
        self.assertEqual(result['css'], 'good')

    def test_medium_chance(self):
        p = self._make_program(100)
        result = get_chance(100, p)
        self.assertEqual(result['css'], 'warning')

    def test_low_chance(self):
        p = self._make_program(100)
        result = get_chance(90, p)
        self.assertEqual(result['css'], 'danger')

    def test_no_chance(self):
        p = self._make_program(100)
        result = get_chance(70, p)
        self.assertEqual(result['css'], 'fail')

    def test_zero_score_returns_none(self):
        p = self._make_program(100)
        result = get_chance(0, p)
        self.assertIsNone(result)


class ProgramViewTest(TestCase):

    def setUp(self):
        self.uni = University.objects.create(name='ЮУрГУ', city='Челябинск')
        self.program = Program.objects.create(
            university=self.uni, name='Программная инженерия',
            degree='bachelor', study_form='full_time',
        )

    def test_list_returns_200(self):
        response = self.client.get(reverse('programs:list'))
        self.assertEqual(response.status_code, 200)

    def test_detail_returns_200(self):
        response = self.client.get(reverse('programs:detail', args=[self.program.pk]))
        self.assertEqual(response.status_code, 200)

    def test_detail_nonexistent_returns_404(self):
        response = self.client.get(reverse('programs:detail', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_calculator_requires_login(self):
        response = self.client.get(reverse('programs:calculator'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response['Location'])

    def test_compare_toggle_add(self):
        response = self.client.post(
            reverse('programs:compare_toggle'),
            {'program_id': self.program.pk},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'added')
        self.assertEqual(data['count'], 1)

    def test_compare_toggle_remove(self):
        self.client.post(reverse('programs:compare_toggle'), {'program_id': self.program.pk})
        response = self.client.post(
            reverse('programs:compare_toggle'),
            {'program_id': self.program.pk},
        )
        data = response.json()
        self.assertEqual(data['status'], 'removed')
        self.assertEqual(data['count'], 0)

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.db import IntegrityError
from apps.universities.models import University
from apps.programs.models import Program, Subject
from .models import ExamResult, Favorite


class ExamResultConstraintTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('testuser', password='pass')
        self.subject = Subject.objects.create(name='Математика')

    def test_exam_result_created(self):
        ExamResult.objects.create(user=self.user, subject=self.subject, score=85)
        self.assertEqual(ExamResult.objects.count(), 1)

    def test_duplicate_subject_raises_error(self):
        ExamResult.objects.create(user=self.user, subject=self.subject, score=85)
        with self.assertRaises(IntegrityError):
            ExamResult.objects.create(user=self.user, subject=self.subject, score=90)


class FavoriteViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('testuser', password='pass')
        uni = University.objects.create(name='ЮУрГУ', city='Челябинск')
        self.program = Program.objects.create(
            university=uni, name='Информатика', code='02.03.02',
            faculty='ФАК', profile='IT', degree='bachelor',
            study_form='full_time',
        )
        self.client.login(username='testuser', password='pass')

    def _post_json(self, url, data):
        import json
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json',
        )

    def test_toggle_add_favorite(self):
        response = self._post_json(
            reverse('users:toggle_favorite'),
            {'program_id': self.program.pk},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'added')
        self.assertTrue(Favorite.objects.filter(user=self.user, program=self.program).exists())

    def test_toggle_remove_favorite(self):
        Favorite.objects.create(user=self.user, program=self.program)
        response = self._post_json(
            reverse('users:toggle_favorite'),
            {'program_id': self.program.pk},
        )
        data = response.json()
        self.assertEqual(data['status'], 'removed')
        self.assertFalse(Favorite.objects.filter(user=self.user, program=self.program).exists())

    def test_toggle_requires_login(self):
        self.client.logout()
        response = self._post_json(
            reverse('users:toggle_favorite'),
            {'program_id': self.program.pk},
        )
        self.assertEqual(response.status_code, 302)

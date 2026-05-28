from django.test import TestCase
from django.urls import reverse


class HomeViewTest(TestCase):

    def test_home_returns_200(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)

    def test_home_without_params_no_results(self):
        response = self.client.get(reverse('core:home'))
        self.assertIsNone(response.context['ege_programs'])

    def test_home_score_range_one_subject(self):
        response = self.client.get(reverse('core:home') + '?s1=1')
        self.assertEqual(response.context['score_min'], 40)
        self.assertEqual(response.context['score_max'], 100)

    def test_home_score_range_two_subjects(self):
        response = self.client.get(reverse('core:home') + '?s1=1&s2=2')
        self.assertEqual(response.context['score_min'], 79)
        self.assertEqual(response.context['score_max'], 200)

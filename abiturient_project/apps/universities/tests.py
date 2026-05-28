from django.test import TestCase
from django.urls import reverse
from .models import University


class UniversityModelTest(TestCase):

    def setUp(self):
        self.uni = University.objects.create(name='ЮУрГУ', city='Челябинск')

    def test_university_str(self):
        self.assertEqual(str(self.uni), 'ЮУрГУ')

    def test_university_created(self):
        self.assertEqual(University.objects.count(), 1)


class UniversityViewTest(TestCase):

    def setUp(self):
        self.uni = University.objects.create(name='ЮУрГУ', city='Челябинск')
        University.objects.create(name='МГУ', city='Москва')

    def test_list_returns_200(self):
        response = self.client.get(reverse('universities:list'))
        self.assertEqual(response.status_code, 200)

    def test_list_shows_all_universities(self):
        response = self.client.get(reverse('universities:list'))
        self.assertEqual(response.context['universities'].count(), 2)

    def test_search_filters_by_name(self):
        response = self.client.get(reverse('universities:list') + '?q=МГУ')
        self.assertEqual(response.context['universities'].count(), 1)

    def test_search_filters_by_city(self):
        response = self.client.get(reverse('universities:list') + '?q=Челябинск')
        self.assertEqual(response.context['universities'].count(), 1)

    def test_detail_returns_200(self):
        response = self.client.get(reverse('universities:detail', args=[self.uni.pk]))
        self.assertEqual(response.status_code, 200)

    def test_detail_nonexistent_returns_404(self):
        response = self.client.get(reverse('universities:detail', args=[9999]))
        self.assertEqual(response.status_code, 404)

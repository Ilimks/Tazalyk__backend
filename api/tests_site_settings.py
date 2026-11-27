from django.contrib.auth.models import Group, User
from rest_framework.test import APITestCase

from .models import SiteSettings

URL = '/api/site-settings/'


class SiteSettingsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.content = User.objects.create_user('content', password='x')
        cls.content.groups.add(Group.objects.get_or_create(name='content_managers')[0])
        cls.hr = User.objects.create_user('hr', password='x')
        cls.hr.groups.add(Group.objects.get(name='hr_managers'))
        cls.boss = User.objects.create_superuser('boss', password='x')

    def test_visitor_reads_default_off(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()['winter_effects'], False)

    def test_visitor_cannot_switch(self):
        response = self.client.patch(URL, {'winter_effects': True}, format='json')
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(SiteSettings.load().winter_effects)

    def test_other_department_cannot_switch(self):
        self.client.force_authenticate(self.hr)
        response = self.client.patch(URL, {'winter_effects': True}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(SiteSettings.load().winter_effects)

    def test_content_manager_switches_on_and_site_sees_it(self):
        self.client.force_authenticate(self.content)
        response = self.client.patch(URL, {'winter_effects': True}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()['winter_effects'], True)
        self.client.force_authenticate(None)
        self.assertIs(self.client.get(URL).json()['winter_effects'], True)

    def test_superuser_switches_off(self):
        SiteSettings.objects.update_or_create(pk=1, defaults={'winter_effects': True})
        self.client.force_authenticate(self.boss)
        response = self.client.patch(URL, {'winter_effects': False}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SiteSettings.load().winter_effects)

    def test_wrong_value_is_rejected(self):
        self.client.force_authenticate(self.content)
        response = self.client.patch(URL, {'winter_effects': 'snow'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SiteSettings.load().winter_effects)

    def test_only_one_settings_row(self):
        self.client.force_authenticate(self.content)
        for value in (True, False, True):
            self.client.patch(URL, {'winter_effects': value}, format='json')
        self.assertEqual(SiteSettings.objects.count(), 1)

    def test_put_and_delete_are_not_allowed(self):
        self.client.force_authenticate(self.boss)
        self.assertEqual(self.client.put(URL, {'winter_effects': True}, format='json').status_code, 405)
        self.assertEqual(self.client.delete(URL).status_code, 405)

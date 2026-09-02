from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auxiliary.models import City, Country, StateProvince


class CepLookupViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='cep@example.com',
            email='cep@example.com',
            password='S3curePass!123',
        )
        self.client.force_login(self.user)
        self.country = Country.objects.create(name='Brasil', iso_alpha2='BR')
        self.pernambuco = StateProvince.objects.create(
            name='Pernambuco',
            abbreviation='PE',
            country=self.country,
        )
        self.paraiba = StateProvince.objects.create(
            name='Paraíba',
            abbreviation='PB',
            country=self.country,
        )

    def get_lookup_response(self, payload):
        provider_response = Mock()
        provider_response.raise_for_status.return_value = None
        provider_response.json.return_value = payload

        with patch('base.ui.views.httpx.get', return_value=provider_response):
            return self.client.get(reverse('app:cep_lookup'), {'cep': '50000000'})

    def test_resolves_homonymous_city_by_provider_ibge_before_name(self):
        wrong_city = City.objects.create(name='Santa Luzia', state=self.pernambuco)
        matching_city = City.objects.create(
            name='Santa Luzia',
            state=self.paraiba,
            ibge_code='2513409',
        )

        response = self.get_lookup_response(
            {
                'logradouro': 'Rua das Flores',
                'bairro': 'Centro',
                'localidade': 'Santa Luzia',
                'uf': 'PB',
                'ibge': '2513409',
            }
        )

        assert response.status_code == 200
        assert response.json()['city_id'] == matching_city.pk
        assert response.json()['city_id'] != wrong_city.pk
        assert response.json()['state_id'] == self.paraiba.pk
        assert response.json()['country_id'] == self.country.pk

    def test_falls_back_to_city_name_within_provider_state_only(self):
        wrong_city = City.objects.create(name='Santa Luzia', state=self.pernambuco)
        matching_city = City.objects.create(name='Santa Luzia', state=self.paraiba)

        response = self.get_lookup_response(
            {
                'logradouro': 'Rua das Flores',
                'bairro': 'Centro',
                'localidade': 'Santa Luzia',
                'uf': 'PB',
                'ibge': '',
            }
        )

        assert response.status_code == 200
        assert response.json()['city_id'] == matching_city.pk
        assert response.json()['city_id'] != wrong_city.pk
        assert response.json()['state_id'] == self.paraiba.pk

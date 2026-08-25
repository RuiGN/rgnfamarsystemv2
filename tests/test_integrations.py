from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient


User = get_user_model()


def create_user(email):
    return User.objects.create_user(username=email, email=email, password='S3curePass!123')


class IntegrationModelTests(TestCase):
    def test_rf28_connectors_clients_and_events_are_globally_safe(self):
        from integrations.models import ApiClientApplication, IntegrationConnector, IntegrationEvent

        owner = create_user('integrations.owner@example.com')
        other_user = create_user('integrations.other@example.com')

        connector = IntegrationConnector.objects.create(
            code='ERP-MAIN',
            name='ERP principal',
            provider_type=IntegrationConnector.ProviderType.ERP,
            base_url='https://erp.example.com/api',
            auth_type=IntegrationConnector.AuthType.API_KEY,
            secret_reference='vault://instances/local/erp-main',
            configuration={'timeout_seconds': 30},
            responsible=owner,
        )
        connector.activate(user=owner)
        connector.record_test_success({'latency_ms': 110, 'secret': 'must-not-be-stored'})
        connector.record_test_failure(
            'Timeout on handshake', {'provider': 'erp', 'token': 'hidden'}
        )
        connector.refresh_from_db()

        api_client = ApiClientApplication.objects.create(
            code='BI-CLIENT',
            name='BI client',
            client_id='bi-client',
            secret_hash='initial',
            scopes=['reports:read', 'masters:read'],
            expires_at=timezone.now() + timedelta(days=90),
            created_by=owner,
        )
        api_client.rotate_secret('NewSecret!123', user=owner)
        api_client.refresh_from_db()

        invalid_connector = IntegrationConnector(
            code='ERP-INVALID',
            name='ERP invalido',
            provider_type=IntegrationConnector.ProviderType.ERP,
            base_url='https://invalid.example.com/api',
            auth_type=IntegrationConnector.AuthType.API_KEY,
            responsible=other_user,
        )
        invalid_client = ApiClientApplication(
            code='CLIENT-INVALID',
            name='Client invalido',
            client_id='client-invalid',
            scopes='reports:read',
            created_by=owner,
        )

        with pytest.raises(ValidationError) as connector_error:
            invalid_connector.full_clean()
        with pytest.raises(ValidationError) as client_error:
            invalid_client.full_clean()

        event_types = set(IntegrationEvent.objects.values_list('event_type', flat=True))
        failure_event = IntegrationEvent.objects.get(
            connector=connector,
            event_type=IntegrationEvent.EventType.TEST_FAILURE,
        )

        assert connector.status == IntegrationConnector.Status.ERROR
        assert connector.last_error == 'Timeout on handshake'
        assert api_client.has_scope('reports:read') is True
        assert api_client.has_scope('finance:write') is False
        assert check_password('NewSecret!123', api_client.secret_hash)
        assert 'secret_reference' in connector_error.value.message_dict
        assert 'scopes' in client_error.value.message_dict
        assert {
            IntegrationEvent.EventType.ACTIVATED,
            IntegrationEvent.EventType.TEST_SUCCESS,
            IntegrationEvent.EventType.TEST_FAILURE,
            IntegrationEvent.EventType.SECRET_ROTATED,
        }.issubset(event_types)
        assert 'token' not in str(failure_event.safe_context).lower()
        assert 'secret' not in str(failure_event.safe_context).lower()


@pytest.mark.legacy_api_permissions
class IntegrationApiVersioningTests(TestCase):
    def test_rf28_versioned_api_logs_secure_context_and_errors(self):
        from integrations.models import ApiCallLog

        user = create_user('integrations.api.versioning@example.com')
        client = APIClient()
        client.force_authenticate(user)

        versioned_response = client.get(
            '/api/v1/accounts/me/?status=active&token=hidden',
            HTTP_AUTHORIZATION='Bearer hidden-token',
        )
        legacy_response = client.get(
            '/api/accounts/me/?module=accounts&secret=hidden',
        )
        missing_response = client.get(
            '/api/v1/missing-route/?password=hidden',
        )

        versioned_log = ApiCallLog.objects.filter(path='/api/v1/accounts/me/').latest('created_at')
        legacy_log = ApiCallLog.objects.filter(path='/api/accounts/me/').latest('created_at')
        missing_log = ApiCallLog.objects.filter(path='/api/v1/missing-route/').latest('created_at')

        assert versioned_response.status_code == 200
        assert legacy_response.status_code == 200
        assert missing_response.status_code == 404
        assert versioned_log.api_version == 'v1'
        assert versioned_log.method == 'GET'
        assert versioned_log.status_code == 200
        assert versioned_log.outcome == ApiCallLog.Outcome.SUCCESS
        assert versioned_log.user == user
        assert not hasattr(versioned_log, 'tenant')
        assert versioned_log.safe_context['query_params'] == {'status': ['active']}
        assert legacy_log.api_version == 'legacy'
        assert legacy_log.safe_context['query_params'] == {'module': ['accounts']}
        assert missing_log.status_code == 404
        assert missing_log.outcome == ApiCallLog.Outcome.ERROR
        assert 'token' not in str(versioned_log.safe_context).lower()
        assert 'secret' not in str(legacy_log.safe_context).lower()
        assert 'password' not in str(missing_log.safe_context).lower()


@pytest.mark.legacy_api_permissions
class IntegrationApiTests(TestCase):
    def test_rf28_integration_api_enforces_permissions_and_actions(self):
        from integrations.models import (
            ApiCallLog,
            ApiClientApplication,
            IntegrationConnector,
            IntegrationEvent,
        )

        user = create_user('integrations.api@example.com')
        other_user = create_user('integrations.other.api@example.com')
        IntegrationConnector.objects.create(
            code='ERP-OTHER',
            name='ERP secundario',
            provider_type=IntegrationConnector.ProviderType.ERP,
            base_url='https://other.example.com/api',
            auth_type=IntegrationConnector.AuthType.API_KEY,
            secret_reference='vault://instances/local/erp-secondary',
            responsible=other_user,
        )
        client = APIClient()
        client.force_authenticate(user)

        connector_response = client.post(
            '/api/integrations/connectors/',
            {
                'code': 'ERP-MAIN',
                'name': 'ERP principal',
                'provider_type': IntegrationConnector.ProviderType.ERP,
                'base_url': 'https://erp.example.com/api',
                'auth_type': IntegrationConnector.AuthType.API_KEY,
                'secret_reference': 'vault://instances/local/erp-main',
                'configuration': {'timeout_seconds': 30},
                'responsible': user.id,
            },
            format='json',
        )
        invalid_user_response = client.post(
            '/api/integrations/connectors/',
            {
                'code': 'ERP-INVALID',
                'name': 'ERP invalido',
                'provider_type': IntegrationConnector.ProviderType.ERP,
                'base_url': 'https://invalid.example.com/api',
                'auth_type': IntegrationConnector.AuthType.API_KEY,
                'responsible': other_user.id,
            },
            format='json',
        )
        connector_id = connector_response.json()['id']
        activate_response = client.post(
            f'/api/integrations/connectors/{connector_id}/activate/',
        )
        failure_response = client.post(
            f'/api/integrations/connectors/{connector_id}/test_failure/',
            {
                'error_message': 'Timeout on handshake',
                'details': {'secret': 'hidden', 'provider': 'erp'},
            },
            format='json',
        )
        api_client_response = client.post(
            '/api/integrations/api-clients/',
            {
                'code': 'BI-CLIENT',
                'name': 'BI client',
                'client_id': 'bi-client',
                'scopes': ['reports:read', 'masters:read'],
                'expires_at': (timezone.now() + timedelta(days=90)).isoformat(),
            },
            format='json',
        )
        api_client_id = api_client_response.json()['id']
        rotate_response = client.post(
            f'/api/integrations/api-clients/{api_client_id}/rotate_secret/',
            {'secret': 'NewSecret!123'},
            format='json',
        )
        connectors_list = client.get('/api/integrations/connectors/')
        logs_list = client.get('/api/integrations/api-call-logs/')
        events_list = client.get('/api/integrations/events/')

        assert connector_response.status_code == 201
        assert 'tenant' not in connector_response.json()
        assert invalid_user_response.status_code == 400
        assert 'secret_reference' in invalid_user_response.json()
        assert activate_response.status_code == 200
        assert activate_response.json()['status'] == IntegrationConnector.Status.ACTIVE
        assert failure_response.status_code == 200
        assert failure_response.json()['status'] == IntegrationConnector.Status.ERROR
        assert api_client_response.status_code == 201
        assert api_client_response.json()['created_by'] == user.id
        assert rotate_response.status_code == 200
        assert 'NewSecret!123' not in str(rotate_response.json())
        assert 'ERP secundario' in {item['name'] for item in connectors_list.json()['results']}
        assert logs_list.status_code == 200
        assert events_list.status_code == 200
        assert ApiCallLog.objects.filter(path__startswith='/api/integrations/').exists()
        assert IntegrationEvent.objects.filter(
            event_type=IntegrationEvent.EventType.SECRET_ROTATED,
            api_client_application_id=api_client_id,
        ).exists()
        assert not hasattr(ApiClientApplication.objects.get(pk=api_client_id), 'tenant')

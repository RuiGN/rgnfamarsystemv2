from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_local_compose_defines_core_services_without_external_secrets():
    compose = yaml.safe_load((ROOT / 'docker-compose.local.yml').read_text())
    services = compose['services']

    assert set(services) == {
        'nginx',
        'app',
        'celery_worker',
        'celery_beat',
        'db',
        'redis',
        'rabbitmq',
    }
    assert 'cloudflared' not in services
    assert services['app']['build'] == {'context': '.'}
    assert services['app']['env_file'] == ['${LOCAL_ENV_FILE:-.env.local}']
    assert services['celery_worker']['image'] == 'rgnfarmasystem:local'
    assert services['app']['healthcheck']['test'][0] == 'CMD-SHELL'
    assert services['app']['healthcheck']['start_period'] == '600s'
    assert services['nginx']['ports'] == ['4127:80']
    assert 'ports' not in services['app']
    for internal_service in ('db', 'redis', 'rabbitmq'):
        assert 'ports' not in services[internal_service]
    assert services['nginx']['depends_on'] == {'app': {'condition': 'service_healthy'}}


def test_local_compose_uses_local_service_endpoints():
    compose = yaml.safe_load((ROOT / 'docker-compose.local.yml').read_text())
    app_env = compose['services']['app']['environment']

    assert app_env['DATABASE_URL'].endswith('@db:5432/${POSTGRES_DB}')
    assert '${POSTGRES_PASSWORD}' in app_env['DATABASE_URL']
    assert app_env['REDIS_URL'].startswith('redis://redis:6379/')
    assert app_env['CELERY_BROKER_URL'].endswith('@rabbitmq:5672//')
    assert '${RABBITMQ_DEFAULT_PASS}' in app_env['CELERY_BROKER_URL']


def test_local_nginx_preserves_host_and_proxy_context():
    source = (ROOT / 'deploy/nginx/local.conf').read_text()

    assert 'server_name control.localhost erp.localhost localhost 127.0.0.1;' in source
    assert 'proxy_set_header Host $host;' in source
    assert 'proxy_set_header X-Forwarded-Proto $scheme;' in source
    assert 'location /static/' in source
    assert 'location /media/' in source
    assert 'proxy_pass http://app:8000;' in source

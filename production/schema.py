from drf_spectacular.extensions import OpenApiAuthenticationExtension


class OperationalActionAuthenticationHeaderScheme(OpenApiAuthenticationExtension):
    """Map the challenge-only authenticator to the Basic scheme it advertises."""

    target_class = 'production.views.OperationalActionAuthenticationHeader'
    name = 'operationalBasicChallenge'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'basic',
        }

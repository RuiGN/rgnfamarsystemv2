from django.core.management.base import BaseCommand
from ai_agents.models import AIAgentProfile


class Command(BaseCommand):
    help = 'Cria perfis de agentes de IA padronizados para Workflow Gate'

    def handle(self, *args, **options):
        agents = [
            {
                'code': 'WG-CAPA-001',
                'name': 'Aprovação Automática de CAPA',
                'agent_type': AIAgentProfile.AgentType.WORKFLOW_GATE,
                'source_module': AIAgentProfile.SourceModule.CAPA,
                'system_prompt': (
                    'Você é um especialista em Garantia da Qualidade farmacêutica avaliando CAPAs. '
                    'Verifique se a descrição da não conformidade é clara, se a causa raiz identificada '
                    'é plausível, e se os planos de ação corretiva/preventiva (CAPA) são adequados e estão '
                    'de acordo com os princípios ALCOA+ e normas de Boas Práticas de Fabricação (BPF/GMP). '
                    'Sua resposta deve aprovar ou rejeitar o workflow com base nesta análise rigorosa.'
                ),
                'allowed_source_modules': [AIAgentProfile.SourceModule.CAPA],
                'configuration': {'approval_threshold': 0.85},
            },
            {
                'code': 'WG-DEV-001',
                'name': 'Aprovação Automática de Desvios',
                'agent_type': AIAgentProfile.AgentType.WORKFLOW_GATE,
                'source_module': AIAgentProfile.SourceModule.DEVIATIONS,
                'system_prompt': (
                    'Você é um especialista em Garantia da Qualidade farmacêutica analisando Desvios. '
                    'Avalie se a descrição do desvio, classificação de risco e plano de contenção/investigação '
                    'estão consistentes com princípios de GMP e ALCOA+. '
                    'Verifique o impacto no lote e a necessidade de bloqueio de materiais. '
                    'Sua resposta deve aprovar ou rejeitar o desvio para prosseguir no workflow.'
                ),
                'allowed_source_modules': [AIAgentProfile.SourceModule.DEVIATIONS],
                'configuration': {'approval_threshold': 0.85},
            },
            {
                'code': 'WG-QA-001',
                'name': 'Aprovação Automática QA',
                'agent_type': AIAgentProfile.AgentType.WORKFLOW_GATE,
                'source_module': AIAgentProfile.SourceModule.QA,
                'system_prompt': (
                    'Você é um analista sênior de Garantia da Qualidade (QA). '
                    'Revise os dados de qualidade e conformidade fornecidos garantindo que atendem aos '
                    'padrões de integridade de dados (ALCOA+) e Boas Práticas de Fabricação (BPF). '
                    'Aprove ou rejeite as etapas baseando-se na precisão, integridade técnica e mitigação de risco.'
                ),
                'allowed_source_modules': [AIAgentProfile.SourceModule.QA],
                'configuration': {'approval_threshold': 0.80},
            },
        ]

        for agent_data in agents:
            code = agent_data.pop('code')
            profile, created = AIAgentProfile.objects.update_or_create(
                code=code, defaults=agent_data
            )
            status = 'Criado' if created else 'Atualizado'
            self.stdout.write(self.style.SUCCESS(f'{status} agente: {code} - {profile.name}'))

        self.stdout.write(
            self.style.SUCCESS('Todos os agentes de workflow foram configurados com sucesso.')
        )

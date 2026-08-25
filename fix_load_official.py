import re

with open('auxiliary/management/commands/load_official_reference_data.py', 'r') as f:
    content = f.read()

# Fix _parse_countries
parse_countries_new = """    @staticmethod
    def _parse_countries(payload):
        countries = {}
        for item in payload:
            name = str(item.get('nome') or '').strip() if isinstance(item, dict) else ''
            if not name:
                raise CommandError('País com identificação inválida recebido do IBGE.')
            if name in countries:
                pass
            countries[name] = {'name': name}
        if 'Brasil' not in countries:
            raise CommandError('Fonte IBGE sem o registro do Brasil.')
        return countries"""
content = re.sub(
    r'    @staticmethod\n    def _parse_countries\(payload\):.*?(?=    @staticmethod\n    def _parse_states)',
    parse_countries_new + '\n\n',
    content,
    flags=re.DOTALL,
)

# Fix _parse_states
parse_states_new = """    @staticmethod
    def _parse_states(payload):
        states = {}
        for item in payload:
            if not isinstance(item, dict):
                raise CommandError('UF com formato inválido recebida do IBGE.')
            numeric_code = str(item.get('id') or '')
            abbreviation = str(item.get('sigla') or '').strip().upper()
            name = str(item.get('nome') or '').strip()
            if len(abbreviation) != 2 or len(numeric_code) != 2 or not name:
                raise CommandError('UF com identificação inválida recebida do IBGE.')
            if abbreviation in states:
                raise CommandError(f'UF duplicada na fonte do IBGE: {abbreviation}.')
            states[abbreviation] = {'name': name, 'abbreviation': abbreviation, 'numeric_code': numeric_code}
        return states"""
content = re.sub(
    r'    @staticmethod\n    def _parse_states\(payload\):.*?(?=    @classmethod\n    def _parse_cities)',
    parse_states_new + '\n\n',
    content,
    flags=re.DOTALL,
)
# wait, _parse_states doesn't have @staticmethod currently, let's fix that
content = re.sub(
    r'    def _parse_states\(payload\):.*?(?=    @classmethod\n    def _parse_cities)',
    parse_states_new + '\n\n',
    content,
    flags=re.DOTALL,
)

# Fix _parse_cities
parse_cities_new = """    @classmethod
    def _parse_cities(cls, payload, states):
        state_by_numeric = {state['numeric_code']: code for code, state in states.items()}
        cities = {}
        for item in payload:
            if not isinstance(item, dict):
                raise CommandError('Município com formato inválido recebido do IBGE.')
            ibge_code = str(item.get('id') or '')
            name = str(item.get('nome') or '').strip()
            abbreviation = cls._city_state_abbreviation(item)
            if not abbreviation and len(ibge_code) == 7:
                abbreviation = state_by_numeric.get(ibge_code[:2], '')
            if abbreviation not in states:
                label = abbreviation or 'desconhecida'
                raise CommandError(f'UF {label} não encontrada para o município {ibge_code}.')
            if len(ibge_code) != 7 or not ibge_code.isdigit() or not name:
                raise CommandError('Município com identificação inválida recebido do IBGE.')
            if ibge_code in cities:
                raise CommandError(f'Município duplicado na fonte do IBGE: {ibge_code}.')
            cities[ibge_code] = {'name': name, 'state': abbreviation}
        return cities"""
content = re.sub(
    r'    @classmethod\n    def _parse_cities\(cls, payload, states\):.*?(?=    @staticmethod\n    def _city_state_abbreviation)',
    parse_cities_new + '\n\n',
    content,
    flags=re.DOTALL,
)

# Fix handle
content = content.replace(
    'country_refs = self._upsert_countries(countries)', 'self._upsert_countries(countries)'
)
content = content.replace(
    "state_refs = self._upsert_states(states, country_refs['BR'])",
    'state_refs = self._upsert_states(states)',
)

# Fix upserts
upserts_new = """    def _upsert_countries(self, countries):
        for name, data in countries.items():
            Country.objects.update_or_create(name=name, defaults={'name': name})

    def _upsert_states(self, states):
        refs = {}
        for code, data in states.items():
            name = data['name']
            obj, _ = StateProvince.objects.update_or_create(name=name, defaults={'name': name})
            refs[code] = obj
        return refs

    def _upsert_cities(self, cities, state_refs):
        for code, data in cities.items():
            name = data['name']
            state_obj = state_refs[data['state']]
            # Since city names aren't unique globally, but are unique within a state ideally (though not always),
            # we'll use name and state for update_or_create. The old code used ibge_code/code.
            # But the models only have name and state.
            City.objects.update_or_create(name=name, state=state_obj, defaults={'name': name, 'state': state_obj})"""

content = re.sub(
    r'    def _upsert_countries.*?def _upsert_currencies',
    upserts_new + '\n\n    def _upsert_currencies',
    content,
    flags=re.DOTALL,
)

# Run the replacement
with open('auxiliary/management/commands/load_official_reference_data.py', 'w') as f:
    f.write(content)

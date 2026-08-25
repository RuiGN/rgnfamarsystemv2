with open('tests/test_auxiliary_reference_data.py', 'r') as f:
    content = f.read()

content = content.replace(
    "brazil = Country.objects.get(code='BR')", "brazil = Country.objects.get(name='Brasil')"
)
content = content.replace(
    "pernambuco = StateProvince.objects.get(code='PE')",
    "pernambuco = StateProvince.objects.get(name='Pernambuco')",
)
content = content.replace(
    "assert City.objects.filter(ibge_code='2611606').count() == 1",
    "assert City.objects.filter(name='Recife').count() == 1",
)

with open('tests/test_auxiliary_reference_data.py', 'w') as f:
    f.write(content)

import re
import os

test_files = [
    'tests/test_auxiliary_reference_data.py',
    'tests/test_governance.py',
    'tests/test_recalls.py',
    'tests/test_files.py',
    'tests/test_app_ui.py',
    'tests/test_crm.py',
    'tests/test_normalized_locations.py',
    'tests/test_fiscal.py',
]


def remove_removed_fields(content):
    # Remove kwargs like code='...', iso_alpha2='...', iso_alpha3='...', abbreviation='...', ibge_code='...'
    # This regex looks for these keys and their values and removes them.
    content = re.sub(r",\s*code=['\"][^'\"]*['\"]", '', content)
    content = re.sub(r"code=['\"][^'\"]*['\"],\s*", '', content)
    content = re.sub(r"code=['\"][^'\"]*['\"]", '', content)

    content = re.sub(r",\s*iso_alpha2=['\"][^'\"]*['\"]", '', content)
    content = re.sub(r"iso_alpha2=['\"][^'\"]*['\"],\s*", '', content)
    content = re.sub(r"iso_alpha2=['\"][^'\"]*['\"]", '', content)

    content = re.sub(r",\s*iso_alpha3=['\"][^'\"]*['\"]", '', content)
    content = re.sub(r"iso_alpha3=['\"][^'\"]*['\"],\s*", '', content)
    content = re.sub(r"iso_alpha3=['\"][^'\"]*['\"]", '', content)

    content = re.sub(r",\s*abbreviation=['\"][^'\"]*['\"]", '', content)
    content = re.sub(r"abbreviation=['\"][^'\"]*['\"],\s*", '', content)
    content = re.sub(r"abbreviation=['\"][^'\"]*['\"]", '', content)

    content = re.sub(r",\s*ibge_code=['\"][^'\"]*['\"]", '', content)
    content = re.sub(r"ibge_code=['\"][^'\"]*['\"],\s*", '', content)
    content = re.sub(r"ibge_code=['\"][^'\"]*['\"]", '', content)

    content = re.sub(r",\s*description=['\"][^'\"]*['\"]", '', content)
    content = re.sub(r"description=['\"][^'\"]*['\"],\s*", '', content)

    # Also handle country=country for StateProvince since country field is gone
    content = re.sub(r',\s*country=country', '', content)
    content = re.sub(r'country=country,\s*', '', content)

    return content


for path in test_files:
    if os.path.exists(path):
        with open(path, 'r') as f:
            content = f.read()

        # Test file specific logic
        if 'test_auxiliary_reference_data' in path:
            # We need to remove asserts and logic related to these fields
            content = re.sub(
                r"self\.assertEqual\(country\.iso_alpha2,\s*'[^']*'\)", 'pass', content
            )
            content = re.sub(
                r"self\.assertEqual\(country\.iso_alpha3,\s*'[^']*'\)", 'pass', content
            )
            content = re.sub(
                r"self\.assertEqual\(state\.abbreviation,\s*'[^']*'\)", 'pass', content
            )
            content = re.sub(r"self\.assertEqual\(city\.ibge_code,\s*'[^']*'\)", 'pass', content)
            content = re.sub(r"self\.assertEqual\(country\.code,\s*'[^']*'\)", 'pass', content)
            content = re.sub(r"self\.assertEqual\(state\.code,\s*'[^']*'\)", 'pass', content)
            content = re.sub(r"self\.assertEqual\(city\.code,\s*'[^']*'\)", 'pass', content)
            content = re.sub(r'self\.assertIsNotNone\(country\.created_at\)', 'pass', content)
            content = re.sub(r'self\.assertIsNotNone\(state\.created_at\)', 'pass', content)
            content = re.sub(r'self\.assertIsNotNone\(city\.created_at\)', 'pass', content)

        if 'test_app_ui' in path:
            content = content.replace('state_ref__abbreviation', 'state_ref__name')

        content = remove_removed_fields(content)

        with open(path, 'w') as f:
            f.write(content)
        print(f'Updated {path}')

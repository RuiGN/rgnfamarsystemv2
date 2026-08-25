import os
import re

MODELS_FILES = [
    'masters/models.py',
    'fiscal/models.py',
    'crm/models.py',
    'governance/models.py',
    'procurement/models.py',
    'audits/models.py',
    'training/models.py',
    'pharmacovigilance/models.py',
    'recalls/models.py',
]

# Add country_ref to models
for filepath in MODELS_FILES:
    if not os.path.exists(filepath):
        continue
    with open(filepath, 'r') as f:
        content = f.read()

    # regex to find state_ref definitions
    # example: state_ref = models.ForeignKey(
    # we want to insert country_ref right after it.

    def repl(m):
        prefix = m.group(1)
        original = m.group(0)
        new_field = f"""{prefix}country_ref = models.ForeignKey(
        'auxiliary.Country',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name='país',
    )
    {original}"""
        return new_field

    if 'country_ref = models.ForeignKey(' not in content:
        content = re.sub(r'([a-z_]*)state_ref = models\.ForeignKey\(', repl, content)
        with open(filepath, 'w') as f:
            f.write(content)

# Now registry.py
REGISTRY_FILE = 'base/ui/registry.py'
with open(REGISTRY_FILE, 'r') as f:
    content = f.read()


def registry_repl(m):
    prefix = m.group(1)
    # Order: complement, city, neighborhood, state, country
    return f"'{prefix}complement',\n                    '{prefix}city_ref',\n                    '{prefix}neighborhood',\n                    '{prefix}state_ref',\n                    '{prefix}country_ref',"


# Reorder in registry:
# Currently might be: complement, neighborhood, state_ref, city_ref
content = re.sub(
    r"'([a-z_]*)complement',\s*'([a-z_]*)neighborhood',\s*'([a-z_]*)state_ref',\s*'([a-z_]*)city_ref',",
    registry_repl,
    content,
    flags=re.MULTILINE,
)

# And also other permutations like complement, neighborhood, city_ref, state_ref ?
# Let's just catch complement, neighborhood, zip, etc and rebuild.
# The prompt: "após o complemento a Cidade, depois o Bairro e depois a UF e inclua após a UF o País"
# So if we see 'complement' followed by neighborhood, state_ref, city_ref, we replace.

with open(REGISTRY_FILE, 'w') as f:
    f.write(content)

print('Patch complete.')

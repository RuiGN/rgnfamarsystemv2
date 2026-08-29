class ActiveModuleSlugConverter:
    regex = r'(?!(?:maintenance)(?:/|\Z))[-a-zA-Z0-9_]+'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value

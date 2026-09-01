"""Central retention policy for regulated GxP records."""

GXP_RETENTION_APP_LABELS = frozenset(
    {
        'audits',
        'capa',
        'changes',
        'deviations',
        'documents',
        'files',
        'production',
        'qa',
        'quality',
        'recalls',
        'risks',
        'training',
    }
)


def requires_gxp_retention(model) -> bool:
    """Return whether physical deletion is forbidden for the model's app."""

    return model._meta.app_label in GXP_RETENTION_APP_LABELS

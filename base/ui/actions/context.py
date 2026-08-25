def available_actions(request, resource, obj=None):
    from base.ui.actions.registry import action_registry

    is_detail = obj is not None
    return tuple(
        config
        for config in action_registry.all()
        if config.model is resource.model
        and config.resource_slug == resource.slug
        and config.detail is is_detail
        and config.is_available(request.user, obj)
    )

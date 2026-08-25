"""Statically allow-listed report executors."""

from reports.executors import finance, fiscal, inventory, procurement, production


__all__ = ('finance', 'fiscal', 'inventory', 'procurement', 'production')

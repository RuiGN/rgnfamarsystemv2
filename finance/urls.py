from rest_framework.routers import DefaultRouter

from finance.views import (
    CashFlowEntryViewSet,
    ChartOfAccountViewSet,
    FinancialAccountViewSet,
    FinancialCategoryViewSet,
    FinancialPeriodClosingViewSet,
    FinancialSettlementViewSet,
    FinancialTitleViewSet,
)


app_name = 'finance'

router = DefaultRouter()
router.register('chart-accounts', ChartOfAccountViewSet, basename='chart-account')
router.register('categories', FinancialCategoryViewSet, basename='category')
router.register('accounts', FinancialAccountViewSet, basename='account')
router.register('titles', FinancialTitleViewSet, basename='title')
router.register('settlements', FinancialSettlementViewSet, basename='settlement')
router.register('cash-flow', CashFlowEntryViewSet, basename='cash-flow')
router.register('period-closings', FinancialPeriodClosingViewSet, basename='period-closing')

urlpatterns = router.urls

from rest_framework.routers import DefaultRouter

from masters.views import (
    BusinessPartnerViewSet,
    MasterCategoryViewSet,
    ProductViewSet,
    SiteViewSet,
    StorageLocationViewSet,
    UnitOfMeasureViewSet,
    WarehouseViewSet,
)


app_name = 'masters'

router = DefaultRouter()
router.register('units', UnitOfMeasureViewSet, basename='unit')
router.register('categories', MasterCategoryViewSet, basename='category')
router.register('products', ProductViewSet, basename='product')
router.register('partners', BusinessPartnerViewSet, basename='partner')
router.register('sites', SiteViewSet, basename='site')
router.register('warehouses', WarehouseViewSet, basename='warehouse')
router.register('locations', StorageLocationViewSet, basename='location')

urlpatterns = router.urls

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from inventory.models import StockBalance, StockLot, StockLotGenealogy, StockMovement
from inventory.serializers import (
    StockBalanceSerializer,
    StockLotGenealogySerializer,
    StockLotSerializer,
    StockMovementSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


class SingleInstanceInventoryViewSet(viewsets.ModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    ordering: tuple[str, ...] = ('-created_at',)

    def get_queryset(self):
        return self.queryset.all()

    def perform_create(self, serializer):
        serializer.save()


class StockLotViewSet(SingleInstanceInventoryViewSet):
    queryset = StockLot.objects.select_related(
        'product', 'supplier', 'source_purchase_receipt_item', 'source_production_order'
    )
    serializer_class = StockLotSerializer
    filterset_fields = (
        'product',
        'lot_number',
        'sublot_number',
        'quality_status',
        'supplier',
        'expiry_date',
    )
    search_fields = (
        'product__code',
        'product__description',
        'lot_number',
        'sublot_number',
        'supplier__legal_name',
    )
    ordering = ('product__code', 'lot_number', 'sublot_number')


class StockBalanceViewSet(SingleInstanceInventoryViewSet):
    queryset = StockBalance.objects.select_related(
        'product', 'lot', 'warehouse', 'location', 'unit'
    )
    serializer_class = StockBalanceSerializer
    filterset_fields = ('product', 'lot', 'warehouse', 'location', 'quality_status')
    search_fields = (
        'product__code',
        'product__description',
        'lot__lot_number',
        'warehouse__name',
        'location__code',
    )
    ordering = ('warehouse__name', 'location__code', 'product__code', 'lot__lot_number')


class StockMovementViewSet(SingleInstanceInventoryViewSet):
    queryset = StockMovement.objects.select_related(
        'product',
        'lot',
        'unit',
        'from_warehouse',
        'from_location',
        'to_warehouse',
        'to_location',
        'created_by',
    )
    serializer_class = StockMovementSerializer
    filterset_fields = ('movement_type', 'product', 'lot', 'quality_status', 'movement_date')
    search_fields = (
        'movement_number',
        'product__code',
        'product__description',
        'lot__lot_number',
        'document_reference',
        'reason',
    )
    ordering = ('-movement_date', '-created_at')


class StockLotGenealogyViewSet(SingleInstanceInventoryViewSet):
    queryset = StockLotGenealogy.objects.select_related(
        'input_lot', 'output_lot', 'unit', 'production_order'
    )
    serializer_class = StockLotGenealogySerializer
    filterset_fields = ('input_lot', 'output_lot', 'relation_type', 'production_order')
    search_fields = (
        'input_lot__lot_number',
        'output_lot__lot_number',
        'document_reference',
        'notes',
    )
    ordering = ('output_lot__lot_number', 'input_lot__lot_number')

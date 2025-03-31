from django.apps import AppConfig


class DataWarehouseConfig(AppConfig):
    name = "data_broker.data_warehouse"

    def ready(self):
        import data_broker.data_warehouse.signals

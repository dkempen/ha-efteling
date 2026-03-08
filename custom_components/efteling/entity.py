# """EftelingEntity class."""

# from __future__ import annotations

# from homeassistant.helpers.device_registry import DeviceInfo
# from homeassistant.helpers.update_coordinator import CoordinatorEntity

# from .const import ATTRIBUTION, DOMAIN, NAME
# from .coordinator import EftelingDataUpdateCoordinator


# class EftelingEntity(CoordinatorEntity[EftelingDataUpdateCoordinator]):
#     """EftelingEntity class."""

#     _attr_attribution = ATTRIBUTION

#     def __init__(self, coordinator: EftelingDataUpdateCoordinator) -> None:
#         """Initialize."""
#         super().__init__(coordinator)
#         self._attr_unique_id = coordinator.config_entry.entry_id
#         self._attr_device_info = DeviceInfo(
#             identifiers={
#                 (
#                     coordinator.config_entry.domain,
#                     coordinator.config_entry.entry_id,
#                 ),
#             },
#         )

#     @property
#     def device_info(self) -> DeviceInfo:
#         """Return device info so all sensors are grouped under one device."""
#         return DeviceInfo(
#             identifiers={(DOMAIN, "efteling")},
#             manufacturer=NAME,
#             name=NAME,
#         )

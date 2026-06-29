"""Config flow — sets up the integration via the Home Assistant UI."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_STREET,
    CONF_UPDATE_INTERVAL_HOURS,
    DEFAULT_STREET,
    DEFAULT_UPDATE_INTERVAL_HOURS,
)


class NemenkomTrashConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup dialog."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            street = user_input[CONF_STREET].strip()
            if not street:
                errors[CONF_STREET] = "street_required"
            else:
                await self.async_set_unique_id(street.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Trash schedule — {street}",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_STREET, default=DEFAULT_STREET): str,
                vol.Optional(
                    CONF_UPDATE_INTERVAL_HOURS,
                    default=DEFAULT_UPDATE_INTERVAL_HOURS,
                ): vol.All(int, vol.Range(min=1, max=720)),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NemenkomTrashOptionsFlow()


class NemenkomTrashOptionsFlow(config_entries.OptionsFlow):
    """Allow changing the street name and refresh interval after setup."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STREET,
                    default=self.config_entry.options.get(
                        CONF_STREET,
                        self.config_entry.data.get(CONF_STREET, DEFAULT_STREET),
                    ),
                ): str,
                vol.Optional(
                    CONF_UPDATE_INTERVAL_HOURS,
                    default=self.config_entry.options.get(
                        CONF_UPDATE_INTERVAL_HOURS,
                        self.config_entry.data.get(
                            CONF_UPDATE_INTERVAL_HOURS, DEFAULT_UPDATE_INTERVAL_HOURS
                        ),
                    ),
                ): vol.All(int, vol.Range(min=1, max=720)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

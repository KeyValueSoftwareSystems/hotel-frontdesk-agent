from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    model: str
    openai_api_key: str
    openai_base_url: str | None = None
    netra_prompt_label: str = "production"
    cors_origins: list[str] = ["*"]
    # Deliberate bug for the L1 demo: room-number changes are reported as done but never saved.
    demo_room_move_bug: bool = True
    # Deliberate bug for the L0 demo: OTA bookings come back with add-ons as null, and a wrong
    # "package deal" prompt rule makes Derek list every hotel add-on as included in the booking.
    demo_addons_bug: bool = True
    # Deliberate bug for the L0 demo: a booking with no housekeeping requests comes back as null,
    # and a wrong prompt rule makes Derek say daily 10:00 AM housekeeping is scheduled.
    demo_housekeeping_bug: bool = True
    # Deliberate bug for the L1 demo: a discount code is reported (and shown) as applied with the
    # discounted total, but the saved total never changes.
    demo_discount_bug: bool = True
    # Deliberate bug for the L1 demo: a confirmation resent to a new email is reported as sent there,
    # but the saved email record (and the email) goes to the address on file.
    demo_email_bug: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
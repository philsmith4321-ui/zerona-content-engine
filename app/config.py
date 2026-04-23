from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    admin_password: str = "changeme"
    app_port: int = 8000
    app_host: str = "0.0.0.0"
    base_url: str = "http://localhost:8000"

    anthropic_api_key: str = ""
    replicate_api_token: str = ""

    buffer_access_token: str = ""
    buffer_fb_profile_id: str = ""
    buffer_ig_profile_id: str = ""

    wp_url: str = ""
    wp_username: str = ""
    wp_app_password: str = ""

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notification_email: str = ""

    # Mailgun (campaign sends only)
    mailgun_api_key: str = ""
    mailgun_domain: str = ""
    mailgun_from_email: str = ""
    mailgun_from_name: str = "White House Chiropractic"
    mailgun_webhook_signing_key: str = ""

    # GoHighLevel (GHL) Integration
    ghl_api_token: str = ""
    ghl_location_id: str = ""
    ghl_api_base_url: str = "https://services.leadconnectorhq.com"
    ghl_api_version: str = "2021-07-28"
    ghl_webhook_secret: str = ""
    ghl_referral_landing_url: str = ""
    ghl_credit_balance_field_id: str = ""
    enable_ghl_test_harness: bool = False

    posts_per_week_fb: int = 4
    posts_per_week_ig: int = 5
    blogs_per_month: int = 2
    generation_day: str = "sunday"
    generation_hour: int = 6

    class Config:
        env_file = ".env"


settings = Settings()

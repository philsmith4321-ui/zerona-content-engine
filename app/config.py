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

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notification_email: str = ""

    posts_per_week_fb: int = 4
    posts_per_week_ig: int = 5
    blogs_per_month: int = 2
    generation_day: str = "sunday"
    generation_hour: int = 6

    class Config:
        env_file = ".env"


settings = Settings()

"""RegWatch configuration using pydantic-settings."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Anthropic
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    # Database
    database_url: str = "postgresql+asyncpg://regwatch:regwatch@localhost:5432/regwatch"

    # SendGrid
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "regwatch@auditchain.ai"
    sendgrid_from_name: str = "RegWatch by AuditChain"
    sendgrid_sender_id: int = 1  # SendGrid verified sender ID for Single Sends
    team_email_recipients: list[str] = []
    newsletter_list_id: str = ""  # SendGrid list ID for newsletter subscribers

    # Slack
    slack_webhook_url: str = ""
    slack_channel: str = "#regulatory-alerts"

    # LinkedIn (optional OAuth)
    linkedin_access_token: str = ""

    # Scheduler
    scrape_hour: int = 6
    scrape_minute: int = 0
    digest_hour: int = 8
    digest_minute: int = 0
    linkedin_post_day: int = 0  # 0=Monday
    linkedin_post_hour: int = 9
    newsletter_send_day: int = 1  # 1st day of month (1-31)

    # Relevance threshold for HIGH impact alerts
    high_impact_alert: bool = True
    rapid_response_threshold: float = 0.7

    # App
    app_name: str = "RegWatch"
    app_env: str = "development"
    log_level: str = "INFO"

    # Sources
    sources: dict = {
        "EU_OFFICIAL_JOURNAL": {
            "name": "EU Official Journal",
            "region": "EU",
            "url": "https://eur-lex.europa.eu/oj/direct-access.html",
            "rss": "https://eur-lex.europa.eu/RSSCOMPONENT/static/technicaldocchannel/OJ_L_EN.xml",
            "enabled": True,
        },
        "EU_AI_OFFICE": {
            "name": "European Commission AI Office",
            "region": "EU",
            "url": "https://digital-strategy.ec.europa.eu/en/policies/european-approach-artificial-intelligence",
            "rss": "https://digital-strategy.ec.europa.eu/en/rss.xml",
            "enabled": True,
        },
        "INDIA_MEITY": {
            "name": "MeitY India",
            "region": "India",
            "url": "https://www.meity.gov.in/",
            "rss": "",
            "enabled": True,
        },
        "INDIA_PRS": {
            "name": "PRS Legislative Research",
            "region": "India",
            "url": "https://prsindia.org/",
            "rss": "https://prsindia.org/rss",
            "enabled": True,
        },
        "NIGERIA_NITDA": {
            "name": "NITDA Nigeria",
            "region": "Nigeria",
            "url": "https://nitda.gov.ng/",
            "rss": "https://nitda.gov.ng/feed/",
            "enabled": True,
        },
        "NIGERIA_NDPC": {
            "name": "NDPC Nigeria",
            "region": "Nigeria",
            "url": "https://ndpc.gov.ng/",
            "rss": "https://ndpc.gov.ng/feed/",
            "enabled": True,
        },
        "KENYA_ICTA": {
            "name": "ICT Authority Kenya",
            "region": "Kenya",
            "url": "https://www.ictauthority.go.ke/",
            "rss": "https://www.ictauthority.go.ke/index.php?format=feed&type=rss",
            "enabled": True,
        },
        "KENYA_ODPC": {
            "name": "ODPC Kenya",
            "region": "Kenya",
            "url": "https://www.odpc.go.ke/",
            "rss": "",
            "enabled": True,
        },
        "SOUTH_AFRICA_DCDT": {
            "name": "DCDT South Africa",
            "region": "South Africa",
            "url": "https://www.gov.za/about-government/government-system/national-government/departments/communications-and-digital-technologies",
            "rss": "https://www.gov.za/rss.xml",
            "enabled": True,
        },
        "SOUTH_AFRICA_INFOREG": {
            "name": "Information Regulator South Africa",
            "region": "South Africa",
            "url": "https://www.inforegulator.org.za/",
            "rss": "https://www.inforegulator.org.za/feed/",
            "enabled": True,
        },
        "AFRICAN_UNION": {
            "name": "African Union CITC",
            "region": "African Union",
            "url": "https://au.int/en/departments/infrastructure-and-energy/infrastructure",
            "rss": "https://au.int/en/rss.xml",
            "enabled": True,
        },
        "RWANDA_MINICT": {
            "name": "MINICT Rwanda",
            "region": "Rwanda",
            "url": "https://www.minict.gov.rw/",
            "rss": "https://www.minict.gov.rw/feed/",
            "enabled": True,
        },
        "OECD_AI": {
            "name": "OECD AI Policy Observatory",
            "region": "Global",
            "url": "https://oecd.ai/en/",
            "rss": "https://oecd.ai/en/feed",
            "enabled": True,
        },
        "ITU_AI": {
            "name": "ITU AI Activities",
            "region": "Global",
            "url": "https://www.itu.int/en/ITU-T/AI/Pages/default.aspx",
            "rss": "https://www.itu.int/net4/wsis/forum/2023/rss/news.ashx",
            "enabled": True,
        },
    }


settings = Settings()

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    app_name: str = "AlphaForgeAI"
    app_version: str = "0.2.0"
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def debug(self) -> bool:
        return not self.is_production


# Single shared instance imported everywhere
settings = Settings()

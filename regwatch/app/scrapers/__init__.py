"""RegWatch scrapers package."""
from app.scrapers.africa import (
    AUScraper,
    DCDTScraper,
    ICTAScraper,
    InfoRegScraper,
    MINICTScraper,
    NDPCScraper,
    NITDAScraper,
    ODPCKenyaScraper,
)
from app.scrapers.eu import ECAIOfficeScraper, EUOfficialJournalScraper
from app.scrapers.global_sources import ITUScraper, OECDScraper
from app.scrapers.india import MeityScraper, PRSScraper

ALL_SCRAPERS = [
    EUOfficialJournalScraper,
    ECAIOfficeScraper,
    MeityScraper,
    PRSScraper,
    NITDAScraper,
    NDPCScraper,
    ICTAScraper,
    ODPCKenyaScraper,
    DCDTScraper,
    InfoRegScraper,
    AUScraper,
    MINICTScraper,
    OECDScraper,
    ITUScraper,
]

__all__ = ["ALL_SCRAPERS"]

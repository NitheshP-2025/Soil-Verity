"""Data models shared by the SoilVerity decision engine.

These are the engine's *input and internal* types. The API layer (Swetha) converts
JSON to these types, and the data layer (Bala) fills ClimateData.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Three growing seasons per year. A rotation covers one full cycle of three.
SEASONS: Tuple[str, ...] = ("kharif", "rabi", "summer")


@dataclass(frozen=True)
class Crop:
    name: str
    family: str
    seasons: Tuple[str, ...]            # seasons in which the crop can be sown
    duration_days: int
    water_need_mm: float                # seasonal crop water requirement
    is_legume: bool = False
    needs_irrigation: bool = False      # cannot be grown rainfed
    equipment: Optional[str] = None     # equipment the farmer must have/hire
    cost_level: int = 3                 # 1 (cheap) .. 5 (expensive)
    labour_level: int = 3               # 1 (light) .. 5 (heavy)
    market_level: int = 3               # 1 (weak market) .. 5 (strong)
    heat_sensitivity: float = 0.5       # 0..1
    drought_sensitivity: float = 0.5    # 0..1
    waterlogging_sensitivity: float = 0.5  # 0..1
    ec_threshold: float = 2.0           # dS/m, salinity level where yield starts to drop
    ph_min: float = 6.0
    ph_max: float = 8.0
    is_fallow: bool = False


# Fallow is a pseudo-crop: no water use, no income, no soil cover.
FALLOW = Crop(
    name="Fallow", family="fallow", seasons=SEASONS, duration_days=0,
    water_need_mm=0.0, cost_level=1, labour_level=1, market_level=1,
    heat_sensitivity=0.0, drought_sensitivity=0.0, waterlogging_sensitivity=0.0,
    ec_threshold=99.0, ph_min=0.0, ph_max=14.0, is_fallow=True,
)


@dataclass
class SoilTest:
    """Soil Health Card values. None means 'not provided'."""
    ph: Optional[float] = None
    ec: Optional[float] = None               # dS/m
    organic_carbon: Optional[float] = None   # %


@dataclass
class Farm:
    water_source: str                        # "canal" | "borewell" | "rainfed"
    start_season: str                        # the next season to be planted
    current_rotation: List[str]              # what the farmer normally grows, one crop per season
    last_crops: List[str] = field(default_factory=list)   # most recent crop last
    soil: SoilTest = field(default_factory=SoilTest)
    # Slider values for: water, soil, cost, risk (any positive scale, e.g. 1..5)
    priorities: Dict[str, float] = field(
        default_factory=lambda: {"water": 3, "soil": 3, "cost": 3, "risk": 3})
    equipment: Set[str] = field(default_factory=set)
    # Share (0..1) of the usual irrigation allowance the farmer can count on. None = unknown.
    irrigation_reliability: Optional[float] = None


# ---- Climate inputs (filled by the data layer) -------------------------------------------

@dataclass(frozen=True)
class RainStats:
    rain_mm: float
    heavy_rain_days: float
    dry_spell_days: float        # longest dry spell in the season


@dataclass(frozen=True)
class WeatherStats:
    et0_mm: float                # seasonal reference evapotranspiration
    heat_days: float             # days above the heat threshold


@dataclass(frozen=True)
class SeasonClimate:
    """Climate for one season after choosing one rainfall source and one soil-moisture source."""
    rain_mm: float
    heavy_rain_days: float
    dry_spell_days: float
    soil_moisture: float         # 0..1 root-zone wetness
    et0_mm: float
    et0_mean: float              # long-term mean ET0 for this season
    heat_days: float


@dataclass
class ClimateData:
    """Nested dicts keyed by source name, then year, then season.

    rain:           {"power": {2016: {"kharif": RainStats(...)}}, "imerg": {...}}
    soil_moisture:  {"smap": {2016: {"kharif": 0.34}}, "merra2": {...}}
    weather:        {2016: {"kharif": WeatherStats(...)}}
    """
    rain: Dict[str, Dict[int, Dict[str, RainStats]]]
    soil_moisture: Dict[str, Dict[int, Dict[str, float]]]
    weather: Dict[int, Dict[str, WeatherStats]]

    def years(self) -> List[int]:
        ys = set(self.weather)
        for d in self.rain.values():
            ys &= set(d)
        for d in self.soil_moisture.values():
            ys &= set(d)
        return sorted(ys)

    def et0_means(self) -> Dict[str, float]:
        out = {}
        for s in SEASONS:
            vals = [self.weather[y][s].et0_mm for y in self.weather if s in self.weather[y]]
            out[s] = sum(vals) / len(vals) if vals else 0.0
        return out

    def resolve(self, rain_src: str, sm_src: str, year: int, season: str,
                et0_mean: float) -> SeasonClimate:
        r = self.rain[rain_src][year][season]
        w = self.weather[year][season]
        return SeasonClimate(
            rain_mm=r.rain_mm, heavy_rain_days=r.heavy_rain_days,
            dry_spell_days=r.dry_spell_days,
            soil_moisture=self.soil_moisture[sm_src][year][season],
            et0_mm=w.et0_mm, et0_mean=et0_mean, heat_days=w.heat_days)


@dataclass(frozen=True)
class Variant:
    """One 'what if' run: a rainfall source, a soil-moisture source and a historical year."""
    rain_source: str
    soil_moisture_source: str
    year: int

    @property
    def combo(self) -> str:
        return f"{self.rain_source}+{self.soil_moisture_source}"


@dataclass(frozen=True)
class Rotation:
    seasons: Tuple[str, ...]
    crops: Tuple[str, ...]

    @property
    def name(self) -> str:
        return " > ".join(self.crops)


@dataclass
class Components:
    """Sub-scores (0..1, higher is better) plus facts the explanation layer can quote."""
    water: float
    soil: float
    econ: float
    risk: float
    legume_count: int
    family_repeats: int
    bare_months: float
    irrigation_needed_mm: float
    stress: Dict[str, bool]

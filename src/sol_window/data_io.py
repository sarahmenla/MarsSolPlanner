"""Loaders for the four data layers. Each loader has a real path AND a
synthetic-fallback path so the pipeline is ALWAYS runnable — do not block on
downloads during the hack.

Real sources (grab whichever you can before 19:00):
  - MOLA DEM tile  ........... https://astrogeology.usgs.gov/search/map/Mars/GlobalSurveyor/MOLA
  - AI4Mars labels ........... https://data.nasa.gov/dataset/AI4Mars
  - MARCI daily maps ......... https://pds-imaging.jpl.nasa.gov/data/mro/mars_reconnaissance_orbiter/marci/
  - Water/ice map (SWIM) ..... https://swim.psi.edu/
"""
from __future__ import annotations
import numpy as np, pandas as pd
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
DATA.mkdir(exist_ok=True)


# ---------- ELEVATION ----------
def load_elevation(tile: str | None = None, shape=(256, 256), seed=0) -> np.ndarray:
    """Return a 2-D elevation array (metres). Falls back to synthetic terrain."""
    if tile and Path(tile).exists():
        import rasterio
        with rasterio.open(tile) as ds:
            return ds.read(1).astype(np.float32)
    rng = np.random.default_rng(seed)
    # Gentle terrain: metres of relief across a ~5 km tile → mostly drivable
    y, x = np.mgrid[0:shape[0], 0:shape[1]] / max(shape)
    # Multi-scale Mars-like terrain: broad basins + mid ridges + fine texture
    z = (
        80 * np.sin(2.5 * x) * np.cos(1.8 * y)
        + 15 * np.sin(7 * x + 1.3) * np.sin(6 * y)
        + 3 * np.sin(19 * x) * np.cos(17 * y)
        + 3 * rng.standard_normal(shape)
    )
    # A prominent ridge line — worth going around
    z += 45 * np.exp(-((x - 0.55) ** 2) / 0.015)
    # Impact crater
    crater_r = np.sqrt((x - 0.75) ** 2 + (y - 0.30) ** 2)
    z -= 20 * np.exp(-crater_r ** 2 / 0.012)
    z += 10 * np.exp(-((crater_r - 0.08) ** 2) / 0.002)  # crater rim
    # Second crater
    crater2 = np.sqrt((x - 0.25) ** 2 + (y - 0.70) ** 2)
    z -= 15 * np.exp(-crater2 ** 2 / 0.014)
    return z.astype(np.float32)


# ---------- TERRAIN CLASS (AI4Mars codes: 0 soil, 1 bedrock, 2 sand, 3 big rock) ----------
def load_terrain_class(shape=(256, 256), seed=1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 2, size=shape)              # soil / bedrock
    # sand patches
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    sand = ((xx - 60) ** 2 + (yy - 180) ** 2 < 40 ** 2) | \
           ((xx - 200) ** 2 + (yy - 90) ** 2 < 30 ** 2)
    base[sand] = 2
    # scattered big rocks
    rocks = rng.random(shape) > 0.995
    base[rocks] = 3
    return base.astype(np.int8)


# ---------- TAU (dust optical depth) TIME SERIES ----------
def load_tau_forecast(n_sols: int = 20, seed=2) -> np.ndarray:
    """τ per sol at 1 sol resolution. Injects a synthetic storm on sols 7–10."""
    rng = np.random.default_rng(seed)
    baseline = 0.5 + 0.05 * np.sin(np.linspace(0, 3, n_sols))
    storm = np.zeros(n_sols)
    profile = np.array([0.7, 1.3, 1.5, 0.9], dtype=np.float32)
    end = min(n_sols, 2 + len(profile))
    if end > 2:
        storm[2:end] = profile[: end - 2]
    noise = 0.05 * rng.standard_normal(n_sols)
    return np.clip(baseline + storm + noise, 0.1, 3.0).astype(np.float32)


# ---------- WATER DEPOSITS ----------
def load_water_deposits() -> pd.DataFrame:
    """Deposit catalog in pixel coordinates (row, col) with a yield estimate."""
    return pd.DataFrame(
        [
            # row, col, depth_m, yield_kg_per_m2, name
            (240, 230, 0.6, 120, "Deposit-A shallow ice sheet"),
            (210, 220, 1.8,  80, "Deposit-B buried lens"),
            (150,  60, 0.4, 200, "Deposit-C RSL-associated"),
            ( 90, 190, 1.2,  40, "Deposit-D neutron-spectrometer hit"),
        ],
        columns=["row", "col", "depth_m", "yield_kg_m2", "name"],
    )

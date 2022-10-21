# Kendall County Farm Card Calculations

## Overview
The purpose of this repository is to openly document the means by which farmland cards are calculated in Kendall County, and to make those methods available to the general public, both for possible replication elsewhere and for accountability to County residents.

## Understanding the Process

Users wishing to understand farm cards in depth and see samples can refer to the **tutorial** folder. This folder has a Jupyter Notebook and sample data to help explain everything. For those who do not have a compatible Python environment to run the code themselves, there is also a `farm-cards.slides.html` file that shows the various outputs as a static deck of presentation slides.

This repository does *not* detail the *valuation* of farm parcels as it applies to Kendall County specifically, though the general process is described in the `farm-cards.ipynb` notebook. The valuation process is the purview of the [Assessment Office](https://kendallcountyil.gov/offices/assessments), and further inquiries in such matters can be directed there.

## The *Actual* Process

Users wishing to see the actual file that KCGIS runs to generate farm cards can refer to the `farm_cards.py` file.

# Using This Tool

If you want to adapt or use this tool, simply activate a Python environment and import the `farm_cards.py` file like a library, then call the `calc_farms` function:

```python
import farm_cards.py

calc_farms(
    pins = 'string of PINs'
)

# Or specify a `pin_file` parameter to read the PINs from text

calc_farms(
    pin_file = 'path to text file'
)
```
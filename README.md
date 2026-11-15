# Soil-Verity

SoilVerity is a Field Shift demo that compares crop rotations against soil inputs, farmer priorities and climate data, and surfaces uncertainty with each recommendation.

## Run the integrated app locally

Requirements: Python 3.10+ and the packages in `requirements.txt`.

From the repository root:

```bash
python -m pip install -r requirements.txt
python backend/server.py
```

Then open **http://localhost:8000** in your browser and choose **Compare crop rotations**. Keep the terminal running while you use the app; press Ctrl+C to stop it. If port 8000 is already in use, stop the other server before starting this one.

The local server connects the TerraLoop frontend to the Python decision engine through `/api/recommendations`, loads crop data from `backend/app/knowledge/crops.csv`, and uses the engine's sample climate generator.

## Demo data notice

This quick-start uses synthetic climate data, and the crop knowledge values and decision-engine settings are placeholders. It is not a live NASA data connection or a validated agronomy tool, and outputs are not yield or income forecasts. Replace and review these data sources before real-world use.

To run the existing engine tests: `cd backend && python -m pytest -q`.

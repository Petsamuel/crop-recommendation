from fastapi import FastAPI, HTTPException
import requests
import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel
from models import WeatherData, Coordinates
from typing import List, Dict
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
import joblib
from sklearn.preprocessing import MinMaxScaler
import logging
import numpy as np
# Load environment variables from the .env file
load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Crop Recommendation API",
    description="API for crop recommendations based on weather and soil data",
    version="0.0.1",
    docs_url="/",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],   
    allow_headers=["*"],   
)
# Initialize cache immediately
FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")


# importing all api keys from the.env file
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
WEATHER_API_URL = os.getenv("WEATHER_API_URL")
GEOCODING_API_URL = os.getenv("GEOCODING_API_URL")
FORECAST_API_URL = os.getenv("FORECAST_API_URL")
WEATHER_API_KEY2 = os.getenv("WEATHER_API_KEY2")
WEATHER_HISTORICAL_API_URL = os.getenv("WEATHER_HISTORICAL_API_URL")
CURRENT_AND_FORECAST_API_URL = os.getenv("CURRENT_AND_FORECAST_API_URL")
CURRENT_IP_ADDRESS = os.getenv("CURRENT_IP_ADDRESS")

# Load crop data from crops.json
with open("crops.json", "r") as f:
    crop_data = json.load(f)

# Load ecological zones data
with open('zones.json', 'r') as f:
    ECOLOGICAL_ZONES = json.load(f)


CROP_DICT = {
    1: 'rice', 2: 'maize', 3: 'chickpea', 4: 'kidneybeans',
    5: 'pigeonpeas', 6: 'mothbeans', 7: 'mungbean', 8: 'blackgram',
    9: 'lentil', 10: 'pomegranate', 11: 'banana', 12: 'mango',
    13: 'grapes', 14: 'watermelon', 15: 'muskmelon', 16: 'apple',
    17: 'orange', 18: 'papaya', 19: 'coconut', 20: 'cotton',
    21: 'jute', 22: 'coffee'
}

# Create state to zone mapping
STATE_TO_ZONE = {}
for zone, data in ECOLOGICAL_ZONES.items():
    for state in data.get('States', []):        STATE_TO_ZONE[state.lower()] = zone

def get_soil_properties_by_location(state: str):
    """Get soil properties based on state location"""
    try:
        state = state.strip().title()
        
        if state.lower().endswith(' state'):
            state = state[:-6]  # Remove ' State' suffix
        zone = STATE_TO_ZONE.get(state.lower())
       
        
        if not zone:
            return None
            
        zone_data = ECOLOGICAL_ZONES[zone]
        return {
            'N': zone_data['N'],
            'P': zone_data['P'],
            'K': zone_data['K'],
            'ph': zone_data['pH'],
            'soil_type': zone_data['Soil'],
            'zone': zone
        }
    except Exception as e:
        logging.error(f"Error getting soil properties for {state}: {e}")
        return None

def get_weather(lat: float, lon: float):
    params = {
        'lat': lat,
        'lon': lon,
        'appid': WEATHER_API_KEY,
        'units': 'metric'
    }
    response = requests.get(WEATHER_API_URL, params=params)
   
    
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Weather data not found")
    data = response.json()
    
    return WeatherData(
        temp=data['main']['temp'],
        humidity=data['main']['humidity'],
        wind_speed=data['wind']['speed'],
        temp_min=data['main']['temp_min'],
        temp_max=data['main']['temp_max'],
        main=data['weather'][0]['main'],
        description=data['weather'][0]['description'],
    )

def get_coordinates(city: str):
    """Get coordinates and state for a city"""
    try:
        params = {
            'q': f"{city},NG",
            'limit': 1,
            'appid': WEATHER_API_KEY
        }
        
        response = requests.get(GEOCODING_API_URL, params=params)
        if response.status_code != 200 or len(response.json()) == 0:
            raise HTTPException(status_code=404, detail="City not found or not in Nigeria")
            
        data = response.json()[0]
        # state = extract_state_from_response(data)
        
        return data['lat'], data['lon'], data['state']
        
    except Exception as e:
        logger.error(f"Error getting coordinates for {city}: {e}")
        raise
# Get weather data for given coordinates

def extract_state_from_response(geocoding_data):
    """Extract and clean state name from geocoding response"""
    try:
        state = geocoding_data.get('state', '')
        
        if state.lower().endswith(' state'):
            state = state[:-6]
            
        state_mappings = {
            'fct': 'FCT',
            'federal capital territory': 'FCT',
            'abuja': 'FCT'
        }
        
        return state_mappings.get(state.lower(), state)
        
    except Exception as e:
        logger.error(f"Error extracting state: {e}")
        return None


# Recommend crops based on weather data
def recommend_crops(weather_data, crop_data):
    temp = weather_data['temp']
    humidity = weather_data['humidity']
    main = weather_data['main']
    description = weather_data['description'].lower()
       
    if temp > 20 and humidity < 50:
        print("High temp, low humidity")
        return crop_data.get("high_temp_low_humidity", [])
    elif 20 >= temp > 15 and humidity >= 50:
        print("Moderate temp, high humidity")
        return crop_data.get("moderate_temp_high_humidity", [])
    elif temp < 15:
        print("Low temp")
        return crop_data.get("low_temp", [])
    elif 'rain' in description:
        print("Rainy")
        return crop_data.get("rainy", [])
    else:
        print("Default")
        return crop_data.get("default", [])
    
def current_weather(lat: float, lon: float):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["temperature_2m", "apparent_temperature", "is_day", "precipitation", "rain", "cloud_cover", "surface_pressure", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"],
	    "hourly": "temperature_2m",
        "timezone": "Africa/Cairo"
    }
    responses = requests.get(WEATHER_API_KEY2, params=params)
    if responses.status_code == 200:
        data = responses.json()
        # Extract specific variables from the current weather data
        current_data = data['current']
        return current_data
    else:
        # Handle the case where the API response is not successful
        return {"error": "Failed to retrieve weather data"}

def historical_weather(lat:float, lon:float, start_date: str, end_date: str):
    params = {
	"latitude": 52.52,
	"longitude": 13.41,
	"start_date": start_date,
	"end_date": end_date,
	"daily": ["temperature_2m_max", "temperature_2m_mean", "sunrise", "sunset", "daylight_duration", "sunshine_duration", "precipitation_sum", "rain_sum", "snowfall_sum", "precipitation_hours"],
	"timezone": "Africa/Cairo"
 }
    responses = requests.get(WEATHER_API_KEY2, params=params)
    if responses.status_code != 200:
        raise HTTPException(status_code=404, detail="Weather data not found")
    data = responses.json()
    return data

def predict_crop(city: str, state: str, weather_data: dict, soil_props: dict):
    """Predict crop based on weather and soil data"""
    try:
        # Load model artifacts
        model = joblib.load('best_crop_model.pkl')
        scaler = joblib.load('scaler.pkl')
        
        # Prepare input data
        input_data = pd.DataFrame([{
            'N': soil_props['N'],
            'P': soil_props['P'],
            'K': soil_props['K'],
            'temperature': weather_data.get('temperature_2m', 25),
            'humidity': weather_data.get('humidity', 60),
            'ph': soil_props['ph'],
            'rainfall': weather_data.get('precipitation', 0)
        }])
        
        # Scale and predict
        input_scaled = scaler.transform(input_data)
        predictions = model.predict(input_scaled)
        
        # Convert predictions to list
        predictions = predictions.tolist()
        
        # Map predictions to crop names
        recommended_crops = [CROP_DICT.get(pred, "Unknown Crop") for pred in predictions]
        
        return {
            "status": "success",
            "location": {
                "city": city,
                "state": state,
                "ecological_zone": soil_props['zone']
            },
            "soil_properties": soil_props,
            "weather": weather_data,
            "recommended_crops": recommended_crops
        }
        
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    
def get_weather_forecast(lat: float, lon: float):
    params = {
        'lat': lat,
        'lon': lon,
        'appid': WEATHER_API_KEY,
        'units': 'metric'
    }
    response = requests.get(WEATHER_API_URL, params=params)
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Weather data not found")
    data = response.json()
    return WeatherData(
        temp=data['main']['temp'],
        humidity=data['main']['humidity'],
        wind_speed=data['wind']['speed'],
        temp_min=data['main']['temp_min'],
        temp_max=data['main']['temp_max'],
        main=data['weather'][0]['main'],
        # description=data['weather'][0]['main'],
    )

@app.get("/current/weather/{city}",  tags=["Weather"], status_code=200)
@cache( expire=300 )
def get_current_weather(city: str):
    try:
        lat, lon, state = get_coordinates(city)
        current_data = current_weather(lat, lon)
        states = extract_state_from_response(state)
        
        if 'error' in current_data:
            return {"status": "error", "detail": current_data['error']}
            
        return {
            "status": "success",
            "data": {
                "location": {
                    "city": city,
                    "state": states,
                    "coordinates": {"lat": lat, "lon": lon}
                },
                "weather": current_data
            }
        }
        
    except HTTPException as e:
        return {"status": "error", "detail": e.detail}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
 
@app.get("/weather/{city}", status_code=200,
    tags=["Weather"],
    summary="Get weather data for a city",
    description="Returns current weather data for the specified city"
         )
def get_weather_only(city: str):
    try:
        lat, lon, state = get_coordinates(city)
        weather_data = get_weather(lat, lon)
        
        return {
            "status": "success",
            "data": {
                "location": {
                    "city": city,
                    "state": state,
                    "coordinates": {"lat": lat, "lon": lon}
                },
                "weather": weather_data.dict()
            }
        }
        
    except HTTPException as e:
        return {"status": "error", "detail": e.detail}
    except ValueError as e:
        return {"status": "error", "detail": "Error processing coordinates"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
 
# TODO:crops to plant in location
@app.get("/cropToPlant/{crops}/{city}", status_code=200, summary="Get crops to plant in a location", description="Returns recommended crops to plant in a location", tags=["Crops"]
    )
@cache( expire=300 )   
def get_crops_to_plant(crops:str, city:str):
    try:
        lat, lon, state = get_coordinates(city)
        print(crops, state)
        
        return {
            crops, state
        }
    except HTTPException as e:
        return {"crop to plant":e.details} 

# Get weather and recommendations for a city
@app.get("/recommend-crops/{city}",
    status_code=200,
    tags=["Recommendations"],
    summary="Get crop recommendations",
    description="Returns recommended crops based on location and conditions")
@cache( expire=300 )
async def recommend_crops(city: str):
    try:
        # Get location and weather data
        lat, lon, state = get_coordinates(city)
        weather_data = current_weather(lat, lon)
        
        if 'error' in weather_data:
            return {"status": "error", "detail": weather_data['error']}
        
        # Get soil properties
        soil_props = get_soil_properties_by_location(state)
        if not soil_props:
            return {"status": "error", "detail": f"No soil data found for {state}"}
            
        # Get prediction
        return predict_crop(city, state, weather_data, soil_props)
        
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    
# api for forecasting
@app.get("/weather/forecast/{city}", status_code=200, tags=["Forecast"])
def get_weather_forecast_and_crop_recommendations(city: str):
    try:
        lat, lon = get_coordinates(city)
        weather_data = get_weather_forecast(lat, lon)
        recommended_crops = recommend_crops(weather_data.dict(), crop_data)
        return {"status": "success", "data": weather_data.dict(), "recommended_crops": recommended_crops}
    except HTTPException as e:
        return {"status": "error", "detail": e.detail}


@app.get("/weather/history/{city}/{start_date}/{end_date}", status_code=200, summary="start_date and end_date: 2022-01-01, 2022-01-31", tags=["History"])
def historical_weather_data(city: str, start_date: str, end_date: str):
    #examples of start_date and end_date: 2022-01-01, 2022-01-31
    lat, lon, state = get_coordinates(city)
    historical_data = historical_weather(lat, lon, start_date, end_date)
    return {"status": "success", "data": historical_data}

#health
@app.get("/health", status_code=200, summary="Check the health of the API", tags=["Health"],)
@cache( expire=300 )
def health():
    # Returns a message describing the status of this service
    return {
        "status":"success",
        "message":"The service is running",
        "timestamp": timestamp(datetime.now()),
        "response_time": 0.1,
        "version": "0.0.1"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=5000)


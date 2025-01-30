from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import requests
import os
import json
import requests_cache
from dotenv import load_dotenv
from pydantic import BaseModel
from models import WeatherData, Coordinates
from typing import List, Dict
from retry_requests import retry
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from datetime import timedelta
import joblib
from sklearn.preprocessing import MinMaxScaler
import numpy as np

# Load environment variables from the .env file
app = FastAPI()
load_dotenv()

FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
security = HTTPBasic()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],   
    allow_headers=["*"],   
)

# importing all api keys from the.env file
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
WEATHER_API_URL = os.getenv("WEATHER_API_URL")
GEOCODING_API_URL = os.getenv("GEOCODING_API_URL")
FORECAST_API_URL = os.getenv("FORECAST_API_URL")
WEATHER_API_KEY2 = os.getenv("WEATHER_API_KEY2")
WEATHER_HISTORICAL_API_URL = os.getenv("WEATHER_HISTORICAL_API_URL")
CURRENT_AND_FORECAST_API_URL = os.getenv("CURRENT_AND_FORECAST_API_URL")
CURRENT_IP_ADDRESS = os.getenv("CURRENT_IP_ADDRESS")

print(USERNAME, PASSWORD)
# Load crop data from crops.json
with open("crops.json", "r") as f:
    crop_data = json.load(f)

# Load the trained model and preprocessed data
model = joblib.load("crop_data.pkl")


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
    params = {
        'q': f"{city},NG",
        'limit': 1,
        'appid': WEATHER_API_KEY
    }
    response = requests.get(GEOCODING_API_URL, params=params)
    if response.status_code != 200 or len(response.json()) == 0:
        raise HTTPException(status_code=404, detail="City not found or not in Nigeria")
    data = response.json()[0]
    return data['lat'], data['lon']

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
        print("Full API response:", data['current'])
        # Extract specific variables from the current weather data
        current_data = data['current']
        return current_data
    else:
        # Handle the case where the API response is not successful
        return {"error": "Failed to retrieve weather data"}

def historical_weather(lat:float, lon:float, start_date: str, end_date: str, ):
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

# Root endpoint
@app.get("/")
def read_root():
    about="Api that recommends growable crops based on weather temperature for a given location and soil texture."
    licenses = {'Full Name':"Samuel Peters", 'socials':{'github':"https://github.com/Petsamuel", "repository":"https://github.com/Petsamuel/weather-crop-API", "LinkedIn":"https:linkedIn.com/in/bieefilled"}, 'year':"2024"}
    
    return {"message": about, "License":licenses }

# Get weather and recommendations for a city
@app.get("/weather/{city}", status_code=200)
def get_weather_only(city: str):
    try:
        lat, lon = get_coordinates(city)
        weather_data = get_weather(lat, lon)
        return {"status": "success", "data": weather_data.dict()}
    except HTTPException as e:
        return {"status": "error", "detail": e.detail}

# api for forecasting
@app.get("/weather/forecast/{city}", status_code=200)
def get_weather_forecast_and_crop_recommendations(city: str, user: str = Depends(authenticate)):
    try:
        lat, lon = get_coordinates(city)
        weather_data = get_weather_forecast(lat, lon)
        recommended_crops = recommend_crops(weather_data.dict(), crop_data)
        return {"status": "success", "data": weather_data.dict(), "recommended_crops": recommended_crops}
    except HTTPException as e:
        return {"status": "error", "detail": e.detail}

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
        description=data['weather'][0]['description']

    )

@app.get("/current/weather/{city}", status_code=200)
def get_current_weather(city: str):
    lat, lon = get_coordinates(city)
    current_data = current_weather(lat, lon)
    return {"status": "success", "data": current_data}

@app.get("/weather/history/{city}/{start_date}/{end_date}")
def historical_weather_data(city: str, start_date: str, end_date: str):
    lat, lon = get_coordinates(city)
    historical_data = historical_weather(lat, lon, start_date, end_date)
    return {"status": "success", "data": historical_data}

# New endpoint to recommend crops using the trained model
@app.get("/recommend-crops/{city}", status_code=200)
def recommend_crops_using_model(city: str, user: str = Depends(authenticate)):
    try:
        lat, lon = get_coordinates(city)
        weather_data = get_weather(lat, lon)
        
        # Preprocess the weather data to match the model's input format
        input_data = pd.DataFrame([{
            'temp': weather_data.temp,
            'humidity': weather_data.humidity,
            'wind_speed': weather_data.wind_speed,
            'temp_min': weather_data.temp_min,
            'temp_max': weather_data.temp_max,
            'main': weather_data.main,
            'description': weather_data.description
        }])
        
        # Make predictions using the trained model
        predictions = model.predict(input_data)
        
        # Return the predictions
        return {"status": "success", "recommended_crops": predictions.tolist()}
    except HTTPException as e:
        return {"status": "error", "detail": e.detail}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=5000)
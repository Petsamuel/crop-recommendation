from fastapi import FastAPI, HTTPException
import requests
import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel
from models import WeatherData, Coordinates
from typing import List, Dict


# Load environment variables from the .env file
app = FastAPI()
load_dotenv()

# importing all api keys from the.env file
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
WEATHER_API_URL = os.getenv("WEATHER_API_URL")
GEOCODING_API_URL = os.getenv("GEOCODING_API_URL")
FORECAST_API_URL = os.getenv("FORECAST_API_URL")

# Load crop data from crops.json
with open("crops.json", "r") as f:
    crop_data = json.load(f)
    
    

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to the Weather Crop API"}


# Get weather and recommendations for a city
@app.get("/weather/{city}", status_code=200)
def get_weather_and_crop_recommendations(city: str):
    try:
        lat, lon = get_coordinates(city)
        weather_data = get_weather(lat, lon)
        recommended_crops = recommend_crops(weather_data.dict(), crop_data)
        return {"status": "success", "data": weather_data.dict(), "recommended_crops": recommended_crops}
    except HTTPException as e:
        return {"status": "error", "detail": e.detail}

# Get coordinates of a city
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

# Get weather data for given coordinates
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
        description=data['weather'][0]['description']
    )

# Recommend crops based on weather data
def recommend_crops(weather_data, crop_data):
    temp = weather_data['temp']
    humidity = weather_data['humidity']
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



# api for forecasting
@app.get("/weather/forecast/{city}", status_code=200)
def get_weather_forecast_and_crop_recommendations(city: str):
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
        description=data['weather'][0]['description']
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
    temp = weather_data["temp"]
    humidity = weather_data["humidity"]
    description = weather_data["description"].lower()
    recommended = []

    if temp > 30 and humidity < 50:
        recommended = crop_data["high_temp_low_humidity"]
    elif 20 <= temp <= 30 and humidity > 60:
        recommended = crop_data["moderate_temp_high_humidity"]
    elif temp < 20:
        recommended = crop_data["low_temp"]
    elif "rain" in description:
        recommended = crop_data["rainy"]
    else:
        recommended = crop_data["default"]
    
    return recommended


# get more than one cities 
@app.get("/weather/forecast", status_code=200)
def get_weather_forecast_and_recommendations_multipleCities(cities: List[str]):
    results = []
    for city in cities:
        try:
            lat, lon = get_coordinates(city)
            weather_data = get_weather_forecast(lat, lon)
            recommended_crops = recommend_crops(weather_data.dict(), crop_data)
            results.append({"city": city, "status": "success", "data": weather_data.dict(), "recommended_crops": recommended_crops})
        except HTTPException as e:
            results.append({"city": city, "status": "error", "detail": e.detail})
    return results

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
        description=data['weather'][0]['description']
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
    temp = weather_data["temp"]
    humidity = weather_data["humidity"]
    description = weather_data["description"].lower()
    recommended = []

    if temp > 30 and humidity < 50:
        recommended = crop_data["high_temp_low_humidity"]
    elif 20 <= temp <= 30 and humidity > 60:
        recommended = crop_data["moderate_temp_high_humidity"]
    elif temp < 20:
        recommended = crop_data["low_temp"]
    elif "rain" in description:
        recommended = crop_data["rainy"]
    else:
        recommended = crop_data["default"]
    
    return recommended


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=5000)


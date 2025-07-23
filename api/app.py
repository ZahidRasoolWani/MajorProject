from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import pickle
import pandas as pd
import numpy as np
from datetime import datetime
import os

app = Flask(__name__)
CORS(app) 
# Extended route mapping with new areas
EXTENDED_ROUTE_MAPPING = {
    # Original popular routes
    'electronic_city_to_koramangala': {'area': 'Electronic City', 'road': 'Hosur Road'},
    'whitefield_to_mg_road': {'area': 'Whitefield', 'road': 'ITPL Main Road'},
    'airport_to_indiranagar': {'area': 'Hebbal', 'road': 'Ballari Road'},
    'hebbal_to_electronic_city': {'area': 'Hebbal', 'road': 'Hebbal Flyover'},
    'koramangala_to_whitefield': {'area': 'Koramangala', 'road': 'Sarjapur Road'},
    'jayanagar_to_mg_road': {'area': 'Jayanagar', 'road': 'Jayanagar 4th Block'},
    'yeshwanthpur_to_electronic_city': {'area': 'Yeshwanthpur', 'road': 'Ballari Road'},
    'indiranagar_to_hebbal': {'area': 'Indiranagar', 'road': 'CMH Road'},
    'btm_to_koramangala': {'area': 'BTM Layout', 'road': 'Silk Board Junction'},
    'hsr_to_whitefield': {'area': 'HSR Layout', 'road': '27th Main Road'},
    'marathahalli_to_electronic_city': {'area': 'Marathahalli', 'road': 'Outer Ring Road'},
    'jp_nagar_to_mg_road': {'area': 'JP Nagar', 'road': 'JP Nagar Metro Station'},
    'malleshwaram_to_indiranagar': {'area': 'Malleshwaram', 'road': 'Malleshwaram Circle'},
    'bannerghatta_to_koramangala': {'area': 'Bannerghatta Road', 'road': 'IIM Junction'},
    'rajajinagar_to_yeshwanthpur': {'area': 'Rajajinagar', 'road': 'Rajajinagar Metro Station'},
    'yelahanka_to_hebbal': {'area': 'Yelahanka', 'road': 'International Airport Road'},
    'banashankari_to_jayanagar': {'area': 'Banashankari', 'road': 'Banashankari Metro Station'},
    'rt_nagar_to_malleshwaram': {'area': 'RT Nagar', 'road': 'RT Nagar Main Road'},
    'vijayanagar_to_rajajinagar': {'area': 'Vijayanagar', 'road': 'Vijayanagar Metro Station'},
    'basavanagudi_to_jayanagar': {'area': 'Basavanagudi', 'road': 'Gandhi Bazaar'},
    'electronic_city_traffic': {'area': 'Electronic City', 'road': 'Hosur Road'},
    'whitefield_traffic': {'area': 'Whitefield', 'road': 'ITPL Main Road'},
    'koramangala_traffic': {'area': 'Koramangala', 'road': 'Sony World Junction'},
    'mg_road_traffic': {'area': 'M.G. Road', 'road': 'Anil Kumble Circle'},
    'indiranagar_traffic': {'area': 'Indiranagar', 'road': '100 Feet Road'},
    'jayanagar_traffic': {'area': 'Jayanagar', 'road': 'Jayanagar 4th Block'},
    'hebbal_traffic': {'area': 'Hebbal', 'road': 'Hebbal Flyover'},
    'yeshwanthpur_traffic': {'area': 'Yeshwanthpur', 'road': 'Ballari Road'},
    
    # New area traffic checks
    'btm_layout_traffic': {'area': 'BTM Layout', 'road': 'BTM 2nd Stage'},
    'hsr_layout_traffic': {'area': 'HSR Layout', 'road': 'HSR Sector 1'},
    'marathahalli_traffic': {'area': 'Marathahalli', 'road': 'Marathahalli Junction'},
    'jp_nagar_traffic': {'area': 'JP Nagar', 'road': 'JP Nagar 1st Phase'},
    'malleshwaram_traffic': {'area': 'Malleshwaram', 'road': 'Sampige Road'},
    'bannerghatta_traffic': {'area': 'Bannerghatta Road', 'road': 'Bannerghatta Road Main'},
    'rajajinagar_traffic': {'area': 'Rajajinagar', 'road': 'Chord Road'},
    'yelahanka_traffic': {'area': 'Yelahanka', 'road': 'Yelahanka New Town'},
    'banashankari_traffic': {'area': 'Banashankari', 'road': 'Banashankari 2nd Stage'},
    'rt_nagar_traffic': {'area': 'RT Nagar', 'road': 'Dollars Colony'},
    'vijayanagar_traffic': {'area': 'Vijayanagar', 'road': 'Chord Road Extension'},
    'basavanagudi_traffic': {'area': 'Basavanagudi', 'road': 'Bull Temple Road'}
}

# Global variables for model and encoders
model = None
le_area = None
le_road = None
le_weather = None
le_roadwork = None
feature_columns = None
reference_data = None

def get_area_characteristics(area):
    """Get area characteristics for better traffic predictions"""
    
    area_info = {
        # IT Hubs - Heavy morning and evening traffic
        'Electronic City': {'type': 'IT_Hub', 'peak_multiplier': 1.3, 'weekend_factor': 0.6},
        'Whitefield': {'type': 'IT_Hub', 'peak_multiplier': 1.3, 'weekend_factor': 0.6},
        'Marathahalli': {'type': 'IT_Hub', 'peak_multiplier': 1.2, 'weekend_factor': 0.7},
        'HSR Layout': {'type': 'IT_Hub', 'peak_multiplier': 1.2, 'weekend_factor': 0.7},
        
        # Commercial Areas - Consistent traffic throughout day
        'M.G. Road': {'type': 'Commercial', 'peak_multiplier': 1.1, 'weekend_factor': 0.8},
        'Indiranagar': {'type': 'Commercial', 'peak_multiplier': 1.1, 'weekend_factor': 0.8},
        'Koramangala': {'type': 'Commercial', 'peak_multiplier': 1.15, 'weekend_factor': 0.75},
        'Malleshwaram': {'type': 'Commercial', 'peak_multiplier': 1.1, 'weekend_factor': 0.8},
        'Rajajinagar': {'type': 'Commercial', 'peak_multiplier': 1.1, 'weekend_factor': 0.8},
        
        # Residential Areas - Lower traffic, weekend shopping spikes
        'Jayanagar': {'type': 'Residential', 'peak_multiplier': 1.0, 'weekend_factor': 0.9},
        'BTM Layout': {'type': 'Residential', 'peak_multiplier': 1.05, 'weekend_factor': 0.85},
        'JP Nagar': {'type': 'Residential', 'peak_multiplier': 1.0, 'weekend_factor': 0.9},
        'Banashankari': {'type': 'Residential', 'peak_multiplier': 1.0, 'weekend_factor': 0.85},
        'RT Nagar': {'type': 'Residential', 'peak_multiplier': 0.9, 'weekend_factor': 0.8},
        'Basavanagudi': {'type': 'Residential', 'peak_multiplier': 0.95, 'weekend_factor': 0.85},
        'Vijayanagar': {'type': 'Residential', 'peak_multiplier': 1.0, 'weekend_factor': 0.85},
        
        # Mixed Areas - Transport hubs, hospitals, etc.
        'Hebbal': {'type': 'Mixed', 'peak_multiplier': 1.1, 'weekend_factor': 0.8},
        'Yeshwanthpur': {'type': 'Mixed', 'peak_multiplier': 1.1, 'weekend_factor': 0.8},
        'Bannerghatta Road': {'type': 'Mixed', 'peak_multiplier': 1.05, 'weekend_factor': 1.2},  # Zoo traffic
        'Yelahanka': {'type': 'Mixed', 'peak_multiplier': 1.1, 'weekend_factor': 0.9}  # Airport
    }
    
    return area_info.get(area, {'type': 'Mixed', 'peak_multiplier': 1.0, 'weekend_factor': 0.8})

def resolve_route_selection(route_key):
    """Resolve route selection to area and road"""
    if route_key in EXTENDED_ROUTE_MAPPING:
        return EXTENDED_ROUTE_MAPPING[route_key]
    else:
        # Default fallback
        return {'area': 'Koramangala', 'road': 'Sony World Junction'}

def load_model_and_encoders():
    """Load the trained model and encoders"""
    global model, le_area, le_road, le_weather, le_roadwork, feature_columns, reference_data
    
    try:
        print("Loading model and encoders...")
        
        # Load model
        with open('traffic_model.pkl', 'rb') as f:
            model = pickle.load(f)
        print("Model loaded successfully")
        
        # Load encoders
        with open('area_encoder.pkl', 'rb') as f:
            le_area = pickle.load(f)
        print("Area encoder loaded")
        
        with open('road_encoder.pkl', 'rb') as f:
            le_road = pickle.load(f)
        print("Road encoder loaded")
            
        with open('weather_encoder.pkl', 'rb') as f:
            le_weather = pickle.load(f)
        print("Weather encoder loaded")
            
        with open('roadwork_encoder.pkl', 'rb') as f:
            le_roadwork = pickle.load(f)
        print("Roadwork encoder loaded")
        
        # Load feature columns
        with open('feature_columns.pkl', 'rb') as f:
            feature_columns = pickle.load(f)
        print("Feature columns loaded")
            
        # Load reference data
        with open('model_reference.pkl', 'rb') as f:
            reference_data = pickle.load(f)
        print("Reference data loaded")
            
        print(f"All files loaded successfully!")
        print(f"Model performance: R² = {reference_data['model_performance']['test_r2']:.3f}")
        print(f"Areas available: {len(reference_data['areas'])}")
        print(f"Roads available: {len(reference_data['roads'])}")
        return True
        
    except Exception as e:
        print(f"Error loading model: {e}")
        print("Check if all .pkl files are in the current directory")
        return False

def predict_traffic_congestion(area, road, traffic_volume, avg_speed, 
                             road_capacity=80, weather="Clear", 
                             incidents=0, env_impact=100, 
                             public_transport=50, signal_compliance=80,
                             parking_usage=70, pedestrian_count=100,
                             day_of_week=None):
    """
    Predict traffic congestion level with enhanced area-based adjustments
    """
    try:
        # Use current day if not specified
        if day_of_week is None:
            day_of_week = datetime.now().weekday()
        
        current_month = datetime.now().month
        is_weekend = 1 if day_of_week >= 5 else 0
        current_hour = datetime.now().hour
        
        # Get area characteristics for better prediction
        area_char = get_area_characteristics(area)
        
        # Apply area-specific adjustments for peak hours
        if 8 <= current_hour <= 11 or 17 <= current_hour <= 21:  # Peak hours
            traffic_volume = int(traffic_volume * area_char['peak_multiplier'])
            road_capacity = min(100, road_capacity * area_char['peak_multiplier'])
        
        # Weekend adjustment
        if is_weekend:
            traffic_volume = int(traffic_volume * area_char['weekend_factor'])
            road_capacity = int(road_capacity * area_char['weekend_factor'])
        
        # Encode categorical variables with error handling
        try:
            area_encoded = le_area.transform([area])[0]
        except ValueError:
            print(f"Warning: Area '{area}' not in training data. Using default.")
            area_encoded = 0  # Default to first area
            
        try:
            road_encoded = le_road.transform([road])[0]
        except ValueError:
            print(f"Warning: Road '{road}' not in training data. Using default.")
            road_encoded = 0  # Default to first road
            
        try:
            weather_encoded = le_weather.transform([weather])[0]
        except ValueError:
            print(f"Warning: Weather '{weather}' not recognized. Using default.")
            weather_encoded = 0  # Default to first weather type
        
        # Calculate travel time index (simplified formula)
        travel_time_index = max(1.0, 1.0 + (road_capacity - 50) / 100)
        
        # Create feature dictionary
        features_dict = {
            'Area_Encoded': area_encoded,
            'Road_Encoded': road_encoded,
            'Traffic_Volume': traffic_volume,
            'Average Speed': avg_speed,
            'Travel Time Index': travel_time_index,
            'Road Capacity Utilization': road_capacity,
            'Incident Reports': incidents,
            'Environmental Impact': env_impact,
            'Public Transport Usage': public_transport,
            'Traffic Signal Compliance': signal_compliance,
            'Parking Usage': parking_usage,
            'Pedestrian and Cyclist Count': pedestrian_count,
            'Weather_Encoded': weather_encoded,
            'Roadwork_Encoded': 0,  # Assume no roadwork
            'DayOfWeek': day_of_week,
            'Month': current_month,
            'Is_Weekend': is_weekend
        }
        
        # Create feature array in correct order
        feature_array = np.array([features_dict[col] for col in feature_columns]).reshape(1, -1)
        
        # Make prediction
        prediction = model.predict(feature_array)[0]
        
        # Calculate confidence based on tree agreement
        tree_predictions = [tree.predict(feature_array)[0] for tree in model.estimators_[:20]]
        prediction_std = np.std(tree_predictions)
        confidence = max(0.7, min(0.98, 1 - (prediction_std / 50)))
        
        return {
            'prediction': round(max(0, min(100, prediction)), 2),
            'confidence': round(confidence, 2),
            'status': 'success',
            'interpretation': get_congestion_interpretation(prediction),
            'recommendations': get_recommendations(prediction, area, weather),
            'input_summary': {
                'area': area,
                'road': road,
                'traffic_volume': traffic_volume,
                'avg_speed': avg_speed,
                'weather': weather,
                'area_type': area_char['type']
            }
        }
        
    except Exception as e:
        return {
            'error': str(e),
            'status': 'error'
        }

def get_congestion_interpretation(congestion_level):
    """Convert congestion level to human-readable interpretation"""
    if congestion_level < 25:
        return {
            'level': 'Low',
            'description': 'Free flowing traffic',
            'color': 'text-green-600'
        }
    elif congestion_level < 50:
        return {
            'level': 'Moderate',
            'description': 'Some delays expected',
            'color': 'text-yellow-600'
        }
    elif congestion_level < 75:
        return {
            'level': 'High',
            'description': 'Significant delays',
            'color': 'text-orange-600'
        }
    else:
        return {
            'level': 'Very High',
            'description': 'Heavy traffic, major delays',
            'color': 'text-red-600'
        }

def get_recommendations(congestion_level, area, weather):
    """Get enhanced recommendations based on prediction"""
    recommendations = []
    
    if congestion_level > 75:
        recommendations.extend([
            "Consider using BMTC bus services",
            "Avoid peak hours (8-11 AM, 5-9 PM)",
            "Plan for extra 30-45 minutes travel time"
        ])
        
        # Metro recommendations for areas with metro connectivity
        metro_areas = ['JP Nagar', 'Banashankari', 'Rajajinagar', 'Vijayanagar', 'Malleshwaram', 'Jayanagar', 'M.G. Road']
        if area in metro_areas:
            recommendations.append("Use Namma Metro - nearby metro station available")
        
    elif congestion_level > 50:
        recommendations.extend([
            "Allow extra 15-20 minutes for your journey",
            "Consider alternate routes if available",
            "Carpooling might be beneficial"
        ])
    elif congestion_level > 25:
        recommendations.extend([
            "Good time to travel with minimal delays",
            "Allow 5-10 minutes buffer time"
        ])
    else:
        recommendations.extend([
            "Excellent time to travel",
            "Normal driving conditions expected"
        ])
    
    # Weather-specific recommendations
    if weather == "Rain":
        recommendations.append("Drive carefully - wet roads, reduced visibility")
    elif weather == "Fog":
        recommendations.append("Use fog lights and drive slowly")
    elif weather == "Windy":
        recommendations.append("Be cautious of strong winds, especially on bridges")
    
    # Enhanced area-specific recommendations
    area_specific = {
        'Electronic City': "Heavy IT traffic during office hours",
        'Whitefield': "Consider Outer Ring Road for faster transit",
        'M.G. Road': "Parking may be limited in this area",
        'Koramangala': "Commercial area - expect heavy traffic during business hours",
        'BTM Layout': "Heavy traffic near Silk Board Junction during peak hours",
        'HSR Layout': "IT area - expect morning and evening rush",
        'Marathahalli': "Outer Ring Road can be heavily congested",
        'JP Nagar': "Metro station available - good public transport option",
        'Malleshwaram': "Commercial area with metro connectivity",
        'Bannerghatta Road': "Zoo and hospital traffic may cause delays",
        'Rajajinagar': "Metro connectivity available for public transport",
        'Yelahanka': "Airport traffic may cause additional congestion",
        'Banashankari': "Metro terminal station - excellent connectivity",
        'RT Nagar': "Residential area - lighter traffic on weekends",
        'Vijayanagar': "Metro station nearby for public transport",
        'Basavanagudi': "Historic area with narrow roads - drive carefully",
        'Hebbal': "Major flyover junction - can be congested during peak hours",
        'Yeshwanthpur': "Railway station area - expect additional traffic",
        'Jayanagar': "Well-connected area with metro and bus services",
        'Indiranagar': "Commercial hub - parking may be challenging"
    }
    
    if area in area_specific:
        recommendations.append(area_specific[area])
    
    return recommendations[:4]  # Limit to 4 recommendations

# Store feedback data
feedback_data = []

@app.route('/')
def home():
    """Home page with traffic prediction interface"""
    if not model:
        if not load_model_and_encoders():
            return "Error: Could not load model. Please check if all .pkl files are present.", 500
    
    return render_template('prediction.html', 
                         areas=reference_data['areas'],
                         roads=reference_data['roads'][:10],  # Limit roads for better UX
                         weather_conditions=reference_data['weather_conditions'],
                         model_performance=reference_data['model_performance'],
                         route_mapping=EXTENDED_ROUTE_MAPPING)

@app.route('/predict', methods=['POST'])
def predict():
    """Handle prediction requests with enhanced area support"""
    try:
        data = request.json
        print(f"Received prediction request: {data}")
        
        # Extract form data with validation
        area = data.get('area')
        road = data.get('road')
        
        if not area or not road:
            return jsonify({
                'error': 'Area and Road are required fields',
                'status': 'error'
            })
        
        traffic_volume = int(data.get('traffic_volume', 30000))
        avg_speed = float(data.get('avg_speed', 35))
        road_capacity = float(data.get('road_capacity', 80))
        weather = data.get('weather', 'Clear')
        incidents = int(data.get('incidents', 0))
        day_of_week = data.get('day_of_week')
        
        if day_of_week is not None:
            day_of_week = int(day_of_week)
        
        # Make prediction with enhanced logic
        result = predict_traffic_congestion(
            area=area,
            road=road,
            traffic_volume=traffic_volume,
            avg_speed=avg_speed,
            road_capacity=road_capacity,
            weather=weather,
            incidents=incidents,
            day_of_week=day_of_week
        )
        
        if result['status'] == 'success':
            # Store prediction for potential feedback
            prediction_id = len(feedback_data)
            feedback_data.append({
                'id': prediction_id,
                'prediction': result,
                'input_data': data,
                'timestamp': datetime.now().isoformat()
            })
            
            result['prediction_id'] = prediction_id
            print(f"Prediction successful: {result['prediction']}% congestion for {area}")
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Prediction error: {e}")
        return jsonify({
            'error': f'Prediction failed: {str(e)}',
            'status': 'error'
        })

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    """Handle user feedback submission"""
    try:
        data = request.json
        prediction_id = data.get('prediction_id')
        feedback_type = data.get('feedback')  # 'correct', 'incorrect', 'unknown'
        actual_congestion = data.get('actual_congestion', None)
        
        print(f"Received feedback: {feedback_type} for prediction {prediction_id}")
        
        # Store feedback
        feedback_entry = {
            'prediction_id': prediction_id,
            'feedback_type': feedback_type,
            'actual_congestion': actual_congestion,
            'timestamp': datetime.now().isoformat()
        }
        
        # For now, we'll just store it in memory and log it
        with open('feedback_log.txt', 'a') as f:
            f.write(f"{datetime.now()}: {feedback_entry}\n")
        
        return jsonify({
            'status': 'success',
            'message': 'Thank you for your feedback! It helps improve our model.',
            'feedback_count': len(feedback_data)
        })
        
    except Exception as e:
        print(f"Feedback error: {e}")
        return jsonify({
            'error': f'Feedback submission failed: {str(e)}',
            'status': 'error'
        })

@app.route('/areas')
def get_areas():
    """Get all available areas for API access"""
    if reference_data:
        return jsonify({
            'areas': reference_data['areas'],
            'total_count': len(reference_data['areas']),
            'area_types': {
                'IT_Hubs': ['Electronic City', 'Whitefield', 'Marathahalli', 'HSR Layout'],
                'Commercial': ['M.G. Road', 'Indiranagar', 'Koramangala', 'Malleshwaram'],
                'Residential': ['Jayanagar', 'BTM Layout', 'JP Nagar', 'Banashankari'],
                'Mixed': ['Hebbal', 'Yeshwanthpur', 'Bannerghatta Road', 'Yelahanka']
            }
        })
    else:
        return jsonify({'error': 'Model not loaded'})

@app.route('/routes')
def get_routes():
    """Get all available route mappings"""
    return jsonify({
        'popular_routes': {k: v for k, v in EXTENDED_ROUTE_MAPPING.items() if 'to' in k},
        'area_checks': {k: v for k, v in EXTENDED_ROUTE_MAPPING.items() if 'traffic' in k},
        'total_routes': len(EXTENDED_ROUTE_MAPPING)
    })

@app.route('/stats')
def stats():
    """Show model statistics and feedback summary"""
    if reference_data:
        return jsonify({
            'model_performance': reference_data['model_performance'],
            'total_predictions': len(feedback_data),
            'areas_covered': len(reference_data['areas']),
            'roads_covered': len(reference_data['roads']),
            'feature_count': len(feature_columns) if feature_columns else 0,
            'route_options': len(EXTENDED_ROUTE_MAPPING),
            'training_info': reference_data.get('training_info', {})
        })
    else:
        return jsonify({'error': 'Model not loaded'})

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy' if model else 'unhealthy',
        'model_loaded': model is not None,
        'encoders_loaded': all([le_area, le_road, le_weather, le_roadwork]),
        'areas_supported': len(reference_data['areas']) if reference_data else 0,
        'enhanced_features': True,
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("Starting Bengaluru Traffic Prediction Web App...")
    print("Project: ~/ModelTraining/webapp/")
    
    # Load model on startup
    if load_model_and_encoders():
        print("All components loaded successfully!")
        print("Enhanced with synthetic data support")
        print("Starting Flask server...")
        print("Access the app at: http://127.0.0.1:5000")
        print("Mobile-friendly responsive design included")
        print("Dark/Light theme toggle available")
        print(f"Supporting {len(reference_data['areas']) if reference_data else 0} areas")
        print("-" * 50)
        
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("Failed to load model components.")
        print("Please ensure all .pkl files are in the webapp directory:")
        print("   • traffic_model.pkl")
        print("   • area_encoder.pkl")
        print("   • road_encoder.pkl")
        print("   • weather_encoder.pkl") 
        print("   • roadwork_encoder.pkl")
        print("   • feature_columns.pkl")
        print("   • model_reference.pkl")